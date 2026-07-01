from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core import models  # noqa: F401 - ensure SQLAlchemy models are imported
from app.core.config import settings
from app.core.database import Base, engine, initialize_database

Base.metadata.create_all(bind=engine)
initialize_database()

app = FastAPI(title=settings.app_name)
app.include_router(router, prefix='/api/v1')
app.mount('/saved_configs', StaticFiles(directory='saved_configs'), name='saved_configs')
app.mount('/reports_output', StaticFiles(directory='reports_output'), name='reports_output')


@app.get('/')
def root():
    return {'status': 'ok', 'service': settings.app_name, 'docs': '/docs', 'dashboard': '/api/v1/dashboard'}
