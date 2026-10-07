from ytpi_app import create_app

app = create_app()

if __name__ == "__main__":
    settings = app.extensions["ytpi_settings"]
    app.run(host=settings.host, port=settings.port, debug=False, threaded=True)
