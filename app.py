from ytpi_app import create_app

app = create_app()


if __name__ == "__main__":
    cfg = app.config["ytpi_config"]
    app.run(host=cfg.host, port=cfg.port)
