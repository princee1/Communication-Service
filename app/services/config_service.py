import os
from dotenv import load_dotenv, find_dotenv
from enum import Enum
from utils.fileIO import JSONFile
from definition import _service
import socket


ENV = ".env"

class MODE(Enum):
    DEV_MODE = 'dev'
    PROD_MODE = 'prod'
    TEST_MODE = 'test'
    
    def toMode(val):
        match val:
            case MODE.DEV_MODE.value:
                return MODE.DEV_MODE
            case MODE.PROD_MODE.value:
                return MODE.PROD_MODE
            case MODE.TEST_MODE:
                return MODE.TEST_MODE.value
            case _:
                return MODE.DEV_MODE
    
    def modeToAddr(mode):
        match mode:
            case MODE.TEST_MODE:
                return "127.0.0.1"
            case _:
                return "127.0.0.1"

@_service.ServiceClass           
class ConfigService(_service.Service):
    
    def __init__(self) -> None:
        super().__init__()
        if not load_dotenv(ENV):
            path = find_dotenv(ENV)
            load_dotenv(path)
        self.config_json_app:JSONFile = None
    
    @staticmethod
    def parseToInt(value:str, default:int | None = None,positive = True): # TODO need to add the build error level
        """
        The function `parseToInt` attempts to convert a string to an integer and returns the integer
        value or a default value if conversion fails.
        
        :param value: The `value` parameter is a string that you want to parse into an integer
        :type value: str
        :param default: The `default` parameter in the `parseToInt` function is used to specify a
        default value that will be returned if the conversion of the input `value` to an integer fails.
        If no `default` value is provided, it defaults to `None`
        :type default: int | None
        :return: The `parseToInt` function is returning the integer value of the input `value` after
        converting it from a string. If the conversion is successful, it returns the integer value. If
        there is an error during the conversion (ValueError, TypeError, OverflowError), it returns the
        `default` value provided as a parameter. If no `default` value is provided, it returns `None`.
        """
        try:
            value = int(value)
            if positive:
                if value < 0:
                    raise ValueError
            return value
        except ValueError as e:
            pass
        except TypeError as e:
            pass
        except OverflowError as e:
            pass
        return default

    def build(self):
        self.set_config_value()
        self.verify()

    def set_config_value(self):
        self.MODE = MODE.toMode(os.getenv('MODE'))
        self.PORT_PUBLIC = ConfigService.parseToInt(os.getenv("PORT_PUBLIC"),3000)
        self.PORT_PRIVATE = ConfigService.parseToInt(os.getenv("PORT_PRIVATE"),5000)
        self.LOG_LEVEL = ConfigService.parseToInt(os.getenv("LOG_LEVEL"), 2)
        self.HTTPS_CERTIFICATE=os.getenv("HTTPS_CERTIFICATE")
        self.HTTPS_KEY =os.getenv("HTTPS_KEY")


        self.SMTP_EMAIL_HOST = os.getenv("SMTP_EMAIL_HOST").upper()
        self.SMTP_EMAIL_PORT = ConfigService.parseToInt(os.getenv("SMTP_EMAIL_PORT"))
        self.SMTP_EMAIL = os.getenv("SMTP_EMAIL")
        self.SMTP_PASS = os.getenv("SMTP_EMAIL_PASS")
        self.SMTP_EMAIL_CONN_METHOD= os.getenv("SMTP_EMAIL_CONN_METHOD")
        self.SMTP_EMAIL_LOG_LEVEL= ConfigService.parseToInt(os.getenv("SMTP_EMAIL_LOG_LEVEL"),0)

        self.IMAP_EMAIL_HOST = os.getenv("IMAP_EMAIL_HOST").upper()
        self.IMAP_EMAIL_PORT = ConfigService.parseToInt(os.getenv("IMAP_EMAIL_PORT"))
        self.IMAP_EMAIL = os.getenv("IMAP_EMAIL")
        self.IMAP_EMAIL_PASS = os.getenv("IMAP_EMAIL_PASS")
        self.IMAP_EMAIL_CONN_METHOD= os.getenv("IMAP_EMAIL_CONN_METHOD")

        self.ASSET_LANG = os.getenv("ASSET_LANG")

        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
        self.TWILIO_AUTH_TOKEN= os.getenv("TWILIO_AUTH_TOKEN")
        self.TWILIO_NUMBER= os.getenv("TWILIO_NUMBER")
        
        self.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
        self.API_KEY = os.getenv("API_KEY")
        self.ON_TOP_SECRET_KEY = os.getenv("ON_TOP_SECRET_KEY")
        self.API_ENCRYPT_TOKEN = os.getenv("API_ENCRYPT_TOKEN")
        self.API_EXPIRATION = ConfigService.parseToInt(os.getenv("API_EXPIRATION"), 3600000000000)
        self.AUTH_EXPIRATION = ConfigService.parseToInt(os.getenv("AUTH_EXPIRATION"), 3600000000000)

    def verify(self):
        if self.API_EXPIRATION < self.AUTH_EXPIRATION:
            # self.API_EXPIRATION = self.AUTH_EXPIRATION
            # raise _service.BuildWarningError("API_EXPIRATION cannot be less than AUTH_EXPIRATION")
            ...

    def __getitem__(self, key):
        return getattr(self, key)
    
    def get(self, key):
        return os.getenv(key)
    
    def load_configApp(self,config_file: str):
        config_json_app = JSONFile(config_file)
        config_file = config_file if config_json_app.exists else None
        #apps_data = config_json_app.data
        self.config_json_app = config_json_app
    
    def destroy(self):
        return super().destroy()
