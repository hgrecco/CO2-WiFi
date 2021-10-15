import os

from dashCO2 import create_app

debug = False if os.environ.get("DASH_DEBUG_MODE") == "False" else True
app = create_app(debug)

if __name__ == "__main__":
    # app.run(debug=debug,
    #         host=os.getenv("HOST", "127.0.0.1"),
    #         port=os.getenv("PORT", "8050"),
    #         )
    app.run(
        debug=debug,
        host=os.getenv("HOST", "0.0.0.0"),
        port=os.getenv("PORT", "5000"),
    )
