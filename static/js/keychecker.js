const keymap = {
    "h": "/",
    "a": "/archief",
    "b": "/berichten",
    "s": "/statistieken",
    "i": "/informatie"
};

let prevKey = null;

$(document).ready(function() {
    // Listen for keydown events on the entire document
    $(document).on('keydown', function(event) {
        console.log(prevKey);
        // Get key and code information
        const key = String(event.key).toLowerCase();

        if (prevKey == "n" && /^[0-9]$/.test(key)) {
            window.location.href = `/object/latest/${key}`;
            prevKey = key;
            return;
        }

        if (/^[0-9]$/.test(key)) {
            window.location.href = `/bericht/latest/${key}`;
            prevKey = key;
            return;
        }

        if (!keymap[key]) {
            prevKey = key;
            return;
        }

        window.location.href = keymap[key];

        // Log the key event details to the console
        console.log(`Key pressed: ${key}`);
        prevKey = key;
    });
});