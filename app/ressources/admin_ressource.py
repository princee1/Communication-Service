from dataclasses import dataclass
from typing import Annotated, Any, List, Optional
from fastapi import Depends, Header, Request, Response,HTTPException,status
from fastapi.responses import JSONResponse
from app.services.assets_service import AssetService
from app.services.security_service import JWTAuthService,SecurityService
from app.services.config_service import ConfigService
from app.utils.dependencies import get_admin_token, get_auth_permission, get_bearer_token, get_client_ip
from app.container import InjectInMethod,Get
from app.definition._ressource import Guard, UseGuard, UseHandler, UsePermission,BaseHTTPRessource,HTTPMethod,HTTPRessource, UsePipe, UseRoles
from app.decorators.permissions import JWTRouteHTTPPermission
from app.classes.auth_permission import AuthPermission, Role,RoutePermission,AssetsPermission
from pydantic import BaseModel, RootModel,field_validator
from app.decorators.handlers import ServiceAvailabilityHandler
from app.decorators.pipes import AuthPermissionPipe
from app.utils.validation import ipv4_validator

ADMIN_PREFIX = 'admin'


async def verify_admin_token(x_admin_token: Annotated[str, Header()]):
    configService:ConfigService = Get(ConfigService)
    
    if x_admin_token == None or x_admin_token != configService.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="X-Admin-Token header invalid")

class AuthPermissionModel(BaseModel):
    issued_for:str
    allowed_routes:dict[str,RoutePermission] 
    allowed_assets:Optional[dict[str,AssetsPermission]]
    roles:Optional[list[str]] = [Role.PUBLIC.value]

    @field_validator('issued_for')
    def check_issued_for(cls,issued_for:str):
        if not ipv4_validator(issued_for):
            raise ValueError('Invalid IP Address')
        return issued_for



@UseRoles([Role.ADMIN])
@UsePermission(JWTRouteHTTPPermission)
@UseHandler(ServiceAvailabilityHandler)
@HTTPRessource(ADMIN_PREFIX)
class AdminRessource(BaseHTTPRessource):

    @InjectInMethod
    def __init__(self,configService:ConfigService,jwtAuthService:JWTAuthService,securityService:SecurityService,assetService:AssetService):
        super().__init__(dependencies=[Depends(verify_admin_token)])
        self.configService = configService
        self.jwtAuthService = jwtAuthService
        self.securityService = securityService
        self.assetService = assetService

    
    @BaseHTTPRessource.HTTPRoute('/invalidate/',methods=[HTTPMethod.DELETE])
    def invalidate_tokens(self,authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()
        self.jwtAuthService.set_generation_id(True)
        tokens = self._create_tokens(authPermission)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"message":"Tokens successfully invalidated",
                                                                    "details": "Even if you're the admin old token wont be valid anymore",
                                                                    "tokens":tokens})

    @BaseHTTPRessource.HTTPRoute('/issue-auth/',methods=[HTTPMethod.GET])
    def issue_auth_token(self,authModel:AuthPermissionModel | List[AuthPermissionModel],authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()
        authModel:list[AuthPermissionModel] = authModel if isinstance(authModel,list) else [authModel]
        temp = self._create_tokens(authModel)
        return JSONResponse(status_code=status.HTTP_200_OK,content={"tokens":temp,"message":"Tokens successfully issued"})

    @UsePipe(AuthPermissionPipe)
    @BaseHTTPRessource.HTTPRoute('/refresh-auth/',methods=[HTTPMethod.GET,HTTPMethod.POST])
    def refresh_auth_token(self,tokens:str |list[str], authPermission=Depends(get_auth_permission)):
        self.jwtAuthService.pingService()
        tokens:list[AuthPermission] = tokens if isinstance(tokens,list) else [tokens]
        tokens = self._create_tokens(tokens)
        return JSONResponse(status_code=status.HTTP_200_OK,content={'tokens':tokens ,"message":"Tokens successfully invalidated"})
    

    def _create_tokens(self,tokens):
        temp ={}
        for token in tokens:
            issued_for = token['issued_for']
            allowed_routes = token['allowed_routes']
            roles = token['roles']
            public = Role.PUBLIC.value
            if public not in roles:
                roles.append(public)
            # allowed_assets = token['allowed_assets']
            api_token  = self.securityService.generate_custom_api_key(issued_for)
            auth_token = self.jwtAuthService.encode_auth_token(allowed_routes,roles,issued_for)
            temp[issued_for]={"api_token":api_token,"auth_token":auth_token}
        return temp 