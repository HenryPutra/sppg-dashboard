from firebase_functions import https_fn
from firebase_admin import initialize_app

# The Firebase Admin SDK initialization in app.py handles its own init,
# but it's safe to ensure it's initialized before the request.
from app import app

@https_fn.on_request(max_instances=10, memory=256)
def sppg_backend(req: https_fn.Request) -> https_fn.Response:
    with app.request_context(req.environ):
        return app.full_dispatch_request()
