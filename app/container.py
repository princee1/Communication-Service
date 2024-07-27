import injector
from inspect import signature
# from dependencies import __DEPENDENCY
from typing import overload, Any
from app.services.module import PARAMETER_KEY,RESOLVED_CLASS_KEY
from app.utils.helper import issubclass_of,reverseDict, is_abstract


class ContainerError(BaseException): pass

class CircularDependencyError(ContainerError):
    pass

class MultipleParameterSameDependencyError(ContainerError):
    pass

class M:  # class test
    AbstractDependency: dict = {}
    def _builder(self): pass

    def build(self): pass


TYPE_KEY = "type"
DEP_KEY = "dep"
PARAM_NAMES_KEY = "param_name"

def issubclass(cls): return issubclass_of(M, cls)

def isabstract(cls): return is_abstract(cls,M)

class Container():

    def __init__(self, D: list[type]) -> None:
        self.app = injector.Injector()
        self.DEPENDENCY_MetaData = {}
        self.D: set[str] = self.load_baseSet(D)
        self.load_dep(D)
        self.buildContainer()

    def bind(self, type, obj, scope=None):
        self.app.binder.bind(type, to=obj, scope=scope)

    def get(self, type:type, scope=None):
        return self.app.get(type, scope)
    
    def getFromClassName(self, classname:str,scope=None):
        return self.app.get(self.DEPENDENCY_MetaData[classname][TYPE_KEY],scope)

    def load_dep(self, D:list[type]):
        for x in D:
            if not self.DEPENDENCY_MetaData.__contains__(x):
                dep, p = self.getSignature(x)
                # ERROR Dependency that is not in the dependency list
                abstractRes = self.getAbstractResolving(x)
                for r in abstractRes.keys():
                    r_dep, r_p = self.getSignature(abstractRes[r][RESOLVED_CLASS_KEY])
                    abstractRes[r][PARAMETER_KEY] = r_p
                    dep = dep.union(r_dep)

                self.DEPENDENCY_MetaData[x.__name__] = {
                    TYPE_KEY: x,
                    DEP_KEY: dep,
                    PARAM_NAMES_KEY: p
                }

    def filter(self,D:list[type]):
        temp: list[type] = []
        for dep in D:
            try: 
                if issubclass(dep): temp.append(dep)
                else: raise TypeError
            except: # catch certain type of error
                pass

        return temp

    def getAbstractResolving(self,typ:M):
        return  typ.AbstractDependency


    def getSignature(self, t: type | Any):
        params = signature(t).parameters.values()
        types: set[str] = set()
        paramNames: list[str] = []
        for p in params:
            repr = p.__str__().split(":")
            temp = repr[1].split(".")
            if temp.__len__() == 1:
                # a BUG or a warning
                continue
            types.add(temp[1])
            paramNames.append(repr[0].strip())

        return types, paramNames

    def load_baseSet(self, D: list[type]):
        t: set[str] = set()
        for d in D:
            t.add(d.__name__)
        return t

    def buildContainer(self):
        while self.D.__len__() != 0:
            no_dep = []
            for x in self.D:
                d: set[str] = self.DEPENDENCY_MetaData[x][DEP_KEY]
                if len(d.intersection(self.D)) == 0:
                    no_dep.append(x)
            if len(no_dep) == 0:
                raise CircularDependencyError
            self.D.difference_update(no_dep)
            for x in no_dep:
                self.inject(x)

    def inject(self, x: str):
        current_type: type = self.DEPENDENCY_MetaData[x][TYPE_KEY]
        if isabstract(current_type):
            return 
        dep: set[str] = self.DEPENDENCY_MetaData[x][DEP_KEY]
        params_names: list[str] = self.DEPENDENCY_MetaData[x][PARAM_NAMES_KEY]
        assert len(dep) == len(
            params_names), "The number of dependency must be same length as the number of params names" # BUG might need to remove the assert
        # ERROR need to verify if the dependency a subclass of the abstract class
        # ERROR need to verify if the key of the abstract resolving is parent class of the resolving class
        # ERROR need to verify if we can inject all parameter in the function
        params = self.toParams(dep, params_names)
        obj = self.createDep(current_type, params)
        self.bind(current_type, obj)

    def toParams(self, dep, params_names):
        params = {}
        i = 0
        for d in dep:
            obj_dep = self.get(self.DEPENDENCY_MetaData[d][TYPE_KEY])
            params[params_names[i]] = obj_dep
            i += 1
        return params

    def createDep(self, typ, params):
        flag = issubclass(typ)
        obj: M = typ(**params)
        if flag:
            obj._builder()
        else:
            # WARNING raise we cant verify the data provided
            pass
        return obj

    @property
    def dependencies(self) -> list[type]: return [ x[TYPE_KEY] for x in self.DEPENDENCY_MetaData.values()]

class A: pass
class B: pass
class C: pass
class D: pass
class E: pass
class F: pass

CONTAINER: Container = Container([A, B, C, D, E, F])
print(CONTAINER.dependencies)

    
def InjectInFunction(func):
    """
    The `InjectInFunction` decorator takes the function and inspect it's signature, if the `CONTAINER` can resolve the 
    dependency it will inject the values. You must call the function with the position parameter format to call 
    the `func` with the rest of the parameters.

    If the parameters of the function founds a dependency two times it will return an error

    `example:: `

    @InjectInFunction
    def test(a: A, b: B, c: C, s:str):
        print(a)
        print(b)
        print(c)
        print(s)

    >>> test(s="ok")
    >>> <__main__.C object at 0x000001A76EC36610>
        <__main__.B object at 0x000001A76EC36810>
        <__main__.A object at 0x000001A76EC3FB90>
        ok
    """
    types, pNames = CONTAINER.getSignature(func)
    params = CONTAINER.toParams(types,pNames)
    def wrapper(*args, **kwargs):
        revparams = reverseDict(params)
        revparams.update(kwargs)
        func(**revparams)
    return wrapper
