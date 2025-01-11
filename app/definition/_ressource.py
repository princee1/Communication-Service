"""
The `BaseResource` class initializes with a `container` attribute assigned from the `CONTAINER`
instance imported from `container`.
"""
from inspect import isclass
from typing import Any, Callable, Dict, Iterable, Mapping, TypeVar, Type, TypedDict
from utils.constant import HTTPHeaderConstant
from services.assets_service import AssetService
from services.security_service import JWTAuthService
from container import Get, Need
from definition._service import S, Service
from fastapi import APIRouter, HTTPException, Request, Response, status
from utils.prettyprint import PrettyPrinter_, PrettyPrinter
import time
import functools
from fastapi import BackgroundTasks
from interface.events import EventInterface
from enum import Enum
from utils.dependencies import APIFilterInject


class DecoratorPriority(Enum):
    PERMISSION = 1
    GUARD = 2
    PIPE = 3
    HANDLER = 4


class UseRole(Enum):
    PUBLIC = 1
    SERVICE = 2
    ADMIN = 3


PATH_SEPARATOR = "/"
DEFAULT_STARTS_WITH = '_api_'


def get_class_name_from_method(func: Callable) -> str:
    return func.__qualname__.split('.')[0]


class MethodStartsWithError(Exception):
    ...


class NextHandlerException(Exception):
    ...


class DecoratorObj:

    def __init__(self, ref_callback: Callable, filter=True):
        self.ref = ref_callback
        self.filter = filter

    def do(self, *args, **kwargs):
        if self.filter:
            return APIFilterInject(self.ref)(*args, **kwargs)
        return self.ref(*args, **kwargs)


class Guard(DecoratorObj):

    def __init__(self):
        super().__init__(self.guard, True)

    def guard(self) -> tuple[tuple, dict]:
        ...


class Handler(DecoratorObj):
    def __init__(self):
        super().__init__(self.handle, False)

    def handle(self, function: Callable, *args, **kwargs):
        ...


class Pipe(DecoratorObj):
    def __init__(self, before: bool):
        self.before = before
        super().__init__(self.pipe, filter=before)

    def pipe(self):
        ...


class Permission(DecoratorObj):

    def __init__(self,):
        super().__init__(self.permission, True)

    def permission(self):
        ...


RESSOURCES: dict[str, type] = {}
PROTECTED_ROUTES: dict[str, list[str]] = {}
ROUTES: dict[str, list[dict]] = {}
METADATA_ROUTES: dict[str, str] = {}
DECORATOR_METADATA: dict[str, dict[str, list[tuple[Callable, float]]]] = {}


def add_protected_route_metadata(class_name: str, method_name: str,):
    if class_name in PROTECTED_ROUTES:
        PROTECTED_ROUTES[class_name].append(method_name)
    else:
        PROTECTED_ROUTES[class_name] = [method_name]


def appends_funcs_callback(func: Callable, wrapper: Callable, priority: DecoratorPriority, touch: float = 0):
    class_name = get_class_name_from_method(func)
    if class_name not in DECORATOR_METADATA:
        DECORATOR_METADATA[class_name] = {}

    if func.__name__ not in DECORATOR_METADATA[class_name]:
        DECORATOR_METADATA[class_name][func.__name__] = []

    DECORATOR_METADATA[class_name][func.__name__].append(
        (wrapper, priority.value + touch))


class HTTPMethod(Enum):
    POST = 'POST'
    GET = 'GET'
    UPDATE = 'UPDATE'
    DELETE = 'DELETE'
    PUT = 'PUT'
    PATCH = 'PATCH'
    OPTIONS = 'OPTIONS'
    ALL = 'ALL'

    @staticmethod
    def to_strs(methods: list[Any] | Any):
        if isinstance(methods, HTTPMethod):
            return [methods.value]
        methods: list[HTTPMethod] = methods
        return [method.value for method in methods]
    
class HTTPExceptionParams(TypedDict):
    status_code:int
    details: Any | None
    headers: dict[str,str] | None = None


class Ressource(EventInterface):

    @staticmethod
    def _build_operation_id(route_name: str, prefix: str, method_name: list[HTTPMethod] | HTTPMethod, operation_id: str) -> str:
        if operation_id != None:
            return operation_id

        return route_name.replace(PATH_SEPARATOR, "_")

    @staticmethod
    def HTTPRoute(path: str, methods: Iterable[HTTPMethod] | HTTPMethod = [HTTPMethod.POST], operation_id: str = None, response_model: Any = None, response_description: str = "Successful Response",
                  responses: Dict[int | str, Dict[str, Any]] | None = None,
                  deprecated: bool | None = None):
        def decorator(func: Callable):
            computed_operation_id = Ressource._build_operation_id(
                path, None, func.__qualname__, operation_id)
            METADATA_ROUTES[func.__qualname__] = computed_operation_id

            class_name = get_class_name_from_method(func)
            kwargs = {
                'path': path,
                'endpoint': func.__name__,
                'operation_id': operation_id,
                'summary': func.__doc__,
                'response_model': response_model,
                'methods': HTTPMethod.to_strs(methods),
                'response_description': response_description,
                'responses': responses,
                'deprecated': deprecated,

            }
            if class_name not in ROUTES:
                ROUTES[class_name] = []

            ROUTES[class_name].append(kwargs)

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def Get(path: str, operation_id: str = None, response_model: Any = None, response_description: str = "Successful Response",
            responses: Dict[int | str, Dict[str, Any]] | None = None,
            deprecated: bool | None = None):
        return Ressource.HTTPRoute(path, HTTPMethod.GET, operation_id, response_model, response_description, responses, deprecated)

    @staticmethod
    def Post(path: str, operation_id: str = None, response_model: Any = None, response_description: str = "Successful Response",
             responses: Dict[int | str, Dict[str, Any]] | None = None,
             deprecated: bool | None = None):
        return Ressource.HTTPRoute(path, HTTPMethod.POST, operation_id, response_model, response_description, responses, deprecated)

    def init_stacked_callback(self):
        if self.__class__.__name__ not in DECORATOR_METADATA:
            return
        M = DECORATOR_METADATA[self.__class__.__name__]
        for f in M:
            if hasattr(self, f):
                stacked_callback = M[f].copy()
                c = getattr(self, f)
                for sc in sorted(stacked_callback, key=lambda x: x[1], reverse=True):
                    sc_ = sc[0]
                    c = sc_(c)
                setattr(self, f, c)

    def __init_subclass__(cls: Type) -> None:
        RESSOURCES[cls.__name__] = cls
        # ROUTES[cls.__name__] = []

    def __init__(self, prefix: str) -> None:
        self.assetService: AssetService = Get(AssetService)
        self.prettyPrinter: PrettyPrinter = PrettyPrinter_
        if not prefix.startswith(PATH_SEPARATOR):
            prefix = PATH_SEPARATOR + prefix
        self.router = APIRouter(prefix=prefix, on_shutdown=[
                                self.on_shutdown], on_startup=[self.on_startup])
        self.init_stacked_callback()
        self._add_routes()
        self._add_handcrafted_routes()
        self.default_response: Dict[int | str, Dict[str, Any]] | None = None

    def get(self, dep: Type[S], scope=None, all=False) -> Type[S]:
        return Get(dep, scope, all)

    def need(self, dep: Type[S]) -> Type[S]:
        return Need(dep)

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass

    def _add_routes(self):
        if self.__class__.__name__ not in ROUTES:
            return

        routes_metadata = ROUTES[self.__class__.__name__]
        for route in routes_metadata:
            kwargs = route.copy()
            kwargs['endpoint'] = getattr(self, kwargs['endpoint'],)
            self.router.add_api_route(**kwargs)

    def _add_handcrafted_routes(self):
        ...

    def _add_event(self):
        ...

    @property
    def routeExample(self):
        pass


R = TypeVar('R', bound=Ressource)


def common_class_decorator(cls: Type[R] | Callable, decorator: Callable, handling_func: Callable | tuple[Callable, ...], start_with: str, **kwargs) -> Type[R] | None:
    if type(cls) == type and isclass(cls):
        if start_with is None:
            raise MethodStartsWithError("start_with is required for class")
        for attr in dir(cls):
            if callable(getattr(cls, attr)) and attr.startswith(start_with):
                handler = getattr(cls, attr)
                if handling_func == None:
                    setattr(cls, attr, decorator(**kwargs)(handler))
                else:
                    setattr(cls, attr, decorator(
                        *handling_func, **kwargs)(handler))  # BUG can be an source of error if not a tuple
        return cls
    return None


def UsePermission(*permission_function: Callable[..., bool] | Permission | Type[Permission], start_with: str = DEFAULT_STARTS_WITH, defau):

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        data = common_class_decorator(func, UsePermission, None, start_with)
        if data != None:
            return data

        func_name = func.__name__
        class_name = get_class_name_from_method(func)
        add_protected_route_metadata(class_name, func_name)

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs):
                if len(kwargs) < 2:
                    raise HTTPException(
                        status_code=status.HTTP_501_NOT_IMPLEMENTED)

                for permission in permission_function:
                    try:
                        if type(permission) == type and issubclass(type(permission),Permission):
                            return permission().do(args, **kwargs)
                        elif isinstance(permission, Permission):
                            return permission.do(*args, **kwargs)
                        else:
                            return permission(*args, **kwargs)
                        # TODO defined in the decorator parameter
                        #token = kwargs[HTTPHeaderConstant.TOKEN_NAME_PARAMETER]
                        # TODO defined in the decorator parameter
                        #issued_for = kwargs[HTTPHeaderConstant.CLIENT_IP_PARAMETER]
                    except Exception as e:
                        raise HTTPException( status_code=status.HTTP_501_NOT_IMPLEMENTED)
                return function(*args, **kwargs)

                # TODO permission callback
                jwtService: JWTAuthService = Get(JWTAuthService)
                # TODO Need to replace the function name with the metadata mapping
                if jwtService.verify_permission(token, class_name, func_name, issued_for):
                    return function(*args, **kwargs)

            return callback
        appends_funcs_callback(func, wrapper, DecoratorPriority.PERMISSION)
        return func
    return decorator


def UseHandler(*handler_function: Callable[[Callable, Iterable[Any], Mapping[str, Any]], Exception | None] | Type[Handler] | Handler, start_with: str = DEFAULT_STARTS_WITH):
    # NOTE it is not always necessary to use this decorator, especially when the function is costly in computation

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        data = common_class_decorator(
            func, UseHandler, handler_function, start_with)
        if data != None:
            return data

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs):
                if len(handler_function) == 0:
                    # BUG print a warning
                    return function(*args, **kwargs)

                for handler in handler_function:
                    try:
                        if type(handler) == type and issubclass(type(handler),Handler):
                            return handler().do(function, *args, **kwargs)
                        elif isinstance(handler, Handler):
                            return handler.do(function, *args, **kwargs)
                        else:
                            return handler(function, *args, **kwargs)
                    except NextHandlerException:
                        continue
                # TODO add custom exception
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return callback
        appends_funcs_callback(func, wrapper, DecoratorPriority.HANDLER)
        return func
    return decorator


def UseGuard(*guard_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[bool, str]] | Type[Guard] | Guard, start_with: str = DEFAULT_STARTS_WITH):
    # INFO guards only purpose is to validate the request
    # NOTE:  be mindful of the order

    # BUG notify the developper if theres no guard_function mentioned
    def decorator(func: Callable | Type[R]) -> Callable | Type[R]:
        data = common_class_decorator(
            func, UseGuard, guard_function, start_with)
        if data != None:
            return data

        def wrapper(target_function: Callable):

            @functools.wraps(target_function)
            def callback(*args, **kwargs):

                for guard in guard_function:
                    # BUG check annotations of the guard function
                    if type(guard) == type and issubclass(type(guard), Guard):
                        flag, message = guard().do(*args, **kwargs)
                    elif isinstance(guard, Guard):
                        flag, message = guard.do(*args, **kwargs)
                    else:
                        flag, message = guard(*args, **kwargs)

                    if not flag:
                        raise HTTPException(
                            status_code=status.HTTP_401_UNAUTHORIZED, detail=message)

                return target_function(*args, **kwargs)
            return callback

        appends_funcs_callback(func, wrapper, DecoratorPriority.GUARD)
        return func
    return decorator


def UsePipe(*pipe_function: Callable[[Iterable[Any], Mapping[str, Any]], tuple[Iterable[Any], Mapping[str, Any]]] | Type[Pipe] | Pipe, before: bool = True, start_with: str = DEFAULT_STARTS_WITH):
    # NOTE be mindful of the order which the pipes function will be called, the list can either be before or after, you can add another decorator, each function must return the same type of value

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        data = common_class_decorator(
            func, UsePipe, pipe_function, start_with, before=before)
        if data != None:
            return data

        def wrapper(function: Callable):

            @functools.wraps(function)
            def callback(*args, **kwargs):
                if before:
                    for pipe in pipe_function:  # verify annotation
                        if type(pipe) == type and issubclass(type(pipe),Pipe):
                            args, kwargs = pipe(before=True).do(*args, kwargs)
                        elif isinstance(pipe, Pipe):
                            args, kwargs = pipe.do(*args, kwargs)
                        else:
                            args, kwargs = pipe(*args, **kwargs)
                    return function(*args, **kwargs)
                else:
                    result = function(*args, **kwargs)
                    for pipe in pipe_function:
                        if type(pipe) == type:
                            result = pipe(before=False).do(result)
                        elif isinstance(pipe, Pipe):
                            result = pipe.do(result)
                        else:
                            result = pipe(result)

                    return result
            return callback

        appends_funcs_callback(func, wrapper, DecoratorPriority.PIPE,
                               touch=0 if before else 0.5)  # TODO 3 or 3.5 if before
        return func
    return decorator


def UseInterceptor(interceptor_function: Callable[[Iterable[Any], Mapping[str, Any]], Type[R] | Callable], start_with: str = DEFAULT_STARTS_WITH):
    raise NotImplementedError

    def decorator(func: Type[R] | Callable) -> Type[R] | Callable:
        data = common_class_decorator(
            func, UseInterceptor, interceptor_function, start_with)
        if data != None:
            return data

        def wrapper(function: Callable):
            @functools.wraps(function)
            def callback(*args, **kwargs):
                return interceptor_function(function, *args, **kwargs)
            return callback

        appends_funcs_callback(func, wrapper, 3)
        return func
    return decorator


def UseRole(*role_function):
    ...
