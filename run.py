from src.app import app, socketio


if __name__ == "__main__":
    run_kwargs = {"host": "0.0.0.0", "port": 5000, "debug": True, "use_reloader": False}
    try:
        import flask_socketio  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        run_kwargs["allow_unsafe_werkzeug"] = True
    socketio.run(app, **run_kwargs)
