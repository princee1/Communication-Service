import functools
import sys
from typing import Callable
from celery import Celery,shared_task
from celery.result import AsyncResult
from app.classes.celery import CeleryTaskNameNotExistsError
from app.services.config_service import ConfigService
from app.services.email_service import EmailSenderService
from app.container import Get, build_container
from app.utils.prettyprint import PrettyPrinter_




CELERY_MODULE_NAME = __name__

def task_name(t:str)-> str:
    
    name = f'{CELERY_MODULE_NAME}.{t}'
    if name not in TASK_REGISTRY:
        raise CeleryTaskNameNotExistsError(name)

if 'worker' in sys.argv:
    PrettyPrinter_.message('Building container for the celery worker')
    build_container(False)

TASK_REGISTRY:dict[str,Callable] = {}
try:

    configService: ConfigService = Get(ConfigService)
    backend_url =  configService.CELERY_BACKEND_URL
    message_broker_url=  configService.CELERY_MESSAGE_BROKER_URL
    print(backend_url)
except :
    backend_url = "redis://localhost/0"
    message_broker_url="redis://localhost/0"


celery_app = Celery('celery_app',
            backend=backend_url,
            broker=message_broker_url
        )

celery_app.conf.update(task_serializer='pickle', accept_content=['pickle'])

# Enable RedBeat Scheduler
celery_app.conf.beat_scheduler = "redbeat.RedBeatScheduler"
celery_app.conf.redbeat_redis_url = backend_url
celery_app.conf.timezone = "UTC"

celery_app.autodiscover_tasks(['app.services'], related_name='celery_service')

def RegisterTask(name:str=None):
    def decorator(task:Callable):
        TASK_REGISTRY[task.__qualname__] = task
        return celery_app.task(name=name)(task)
    return decorator

def RegisterTask(name:str=None):
    def decorator(task:Callable):
        TASK_REGISTRY[task.__qualname__] = task
        return shared_task(name=name)(task)
    return decorator

    

@RegisterTask
def task_send_template_mail(data, meta, images):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendTemplateEmail(data, meta, images)
    
@RegisterTask
def task_send_custom_mail(content, meta, images, attachment):
    emailService:EmailSenderService = Get(EmailSenderService)
    return emailService.sendCustomEmail(content, meta, images, attachment)

