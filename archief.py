import base64
from dataclasses import dataclass
from io import BytesIO
from PIL import Image
from quart import Quart, render_template, request, session, g, config
from quart_db import QuartDB
import requests
import urllib.parse
import uuid

app = Quart(__name__, template_folder="templates/", static_folder="static")
db = QuartDB(app, url="sqlite:///db.sqlite")

@dataclass
class MenuItem:
    pos: int
    label: str
    path: str
    right: bool = False
    

class Object:
    def __init__(self, cat_id: str):
        # print(cat_id)
        self.col_name, self.i = cat_id.split("_")
        self.i = int(self.i)
        print(f"Collection: {self.col_name}, Index: {self.i}")
        
    
    async def load_values(self):
        self.col_id = await g.connection.fetch_val("SELECT id FROM collections WHERE name=:name", {"name": self.col_name})
        obj_info = await g.connection.fetch_one("SELECT * FROM objects WHERE collection=:col_id AND \"index\"=:index", {"col_id": self.col_id, "index": self.i})
        if not obj_info:
            raise ValueError("Object not found.")
        
        self.id = obj_info["id"]
        self.type_id = obj_info["type"]
        
        type_info = await g.connection.fetch_one("SELECT * FROM object_types WHERE id=:id", {"id": self.type_id})
        if not type_info:
            raise ValueError("Type not found.")
        
        self.type_name = type_info["name"]
        try:
            self.meta_layout = list(map(int, type_info["meta_layout"].split(",")))
        except ValueError as e:
            self.meta_layout = []
        
        meta_fields = await g.connection.fetch_all("SELECT * FROM meta_values WHERE object_id=:id", {"id": self.id})
        self.meta_fields = {}
        for field in meta_fields:
            field_info = await g.connection.fetch_one("SELECT * FROM meta_fields WHERE id=:id", {"id": field["field_id"]})
            self.meta_fields[field["field_id"]] = {
                "name": field_info["name"], 
                "type": field_info["type"], 
                "value": field["value"]
            }
            
        return self
    
    def get_value_by_name(self, name: str):
        res = list(filter(lambda x: x["name"] == name, self.meta_fields.values()))
        return res[0]["value"] if res else None
        

class Message:
    def __init__(self, id):
        self.id = int(id)
        
    async def load_values(self):
        m_info = await g.connection.fetch_one("SELECT * FROM messages WHERE id=:id", {"id": self.id})
        self.title = m_info["title"]
        self.date = m_info["date"]
        self.author = m_info["author"]
        self.content = m_info["content"]
    
    @staticmethod
    async def get_latest(n: int = 10, s: int = 0):
        latest_ids = map(lambda x: x["id"], await g.connection.fetch_all("SELECT id FROM messages ORDER BY id DESC LIMIT :n", {"n": n}))
        latest = []
        for i in latest_ids:
            msg = Message(i)
            await msg.load_values()
            latest.append(msg)
            
        print(latest)
            
        return latest


app.config["menu"] = sorted([
    MenuItem(0, "Home", "/"),
    MenuItem(1, "Archief", "/archief"),
    MenuItem(2, "Berichten", "/berichten"),
    MenuItem(3, "Statistieken", "/statistieken"),
    MenuItem(4, "Informatie", "/informatie", True)
], key=lambda x: x.pos)

app.config["get_uuid"] = lambda: str(uuid.uuid4())

@app.before_serving
async def register_filters():
    app.jinja_env.filters['uuid'] = lambda x: str(uuid.uuid4())
    app.jinja_env.filters['urlencode'] = lambda x: urllib.parse.quote_plus(x, safe="/")

@app.route("/")
async def home():
    latest_objs_info = await g.connection.fetch_all("SELECT id, collection, \"index\" FROM objects ORDER BY id DESC LIMIT 10;")
    g.latest_objs = []
    for obj in latest_objs_info:
        obj["col_name"] = await g.connection.fetch_val("SELECT name FROM collections WHERE id=:col_id", {"col_id": obj["collection"]})
        obj["name"] =  await g.connection.fetch_val("SELECT value FROM meta_values WHERE field_id=1 AND object_id=:obj_id", {"obj_id": obj["id"]})
        g.latest_objs.append(obj)
        
    g.latest_msgs = Message.get_latest()
    
    return await render_template("home.html")

@app.route("/archief")
async def archief():
    return await render_template("archief.html")

@app.route("/berichten")
async def berichten():
    g.latest_msgs = Message.get_latest()
    return await render_template("berichten.html")

# @app.route("/bericht/latest", defaults={"i": 0})
# @app.route("/bericht/latest/<int:i>")
# async def bericht_latest(i):
#     return await render_template("bericht.html")

@app.route("/bericht/<int:msg_id>")
async def bericht(msg_id):
    g.msg = Message(msg_id)
    await g.msg.load_values()
    return await render_template("bericht.html")

@app.route("/statistieken")
async def statistieken():
    return await render_template("stats.html")

@app.route("/informatie")
async def informatie():
    g.c_info = requests.get("https://svia.nl/api/committees/archief/").json()
    g.c_page_content = requests.get("https://svia.nl/api/pages/render/nl/commissie/archief/").json()["content"]
    
    for i, m in enumerate(g.c_info["group"]["users"]):
        if m["id"] == g.c_info["coordinator"]["id"]:
            m["coordinator"] = True
        else:
            m["coordinator"] = False
        
        img = Image.open(BytesIO(requests.get(f"https://svia.nl/users/{m['id']}/avatar/").content))
        width, height = img.size
        size = min(width, height)
        img = img.crop(((width - size) // 2, (height - size) // 2,
                            (width + size) // 2, (height + size) // 2))
        img = img.resize((75, 75), Image.NEAREST)
        img = img.convert("P", palette=Image.ADAPTIVE, colors=32)
        # img = img.convert("1")
        img = img.resize((400, 400), Image.NEAREST)
        img_byte_array = BytesIO()
        img.save(img_byte_array, format='PNG')
        img_byte_array.seek(0) 
        m["img"] = base64.b64encode(img_byte_array.read()).decode('utf-8')
    
    
    
    return await render_template("info.html")

@app.route("/archief/object/<string:cat_id>")
async def object_p(cat_id):
    # print(urllib.parse.unquote_plus(cat_id))
    try:
        g.obj = Object(urllib.parse.unquote_plus(cat_id))
        print(g.obj)
        await g.obj.load_values()
    except Exception as e:
        print(e)
        return "Invalid catalogue ID"
    return await render_template("object.html")


if __name__ == "__main__":
    app.run(debug=True, port=1953)
