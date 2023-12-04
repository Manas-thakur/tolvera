'''
TODO: save/load? serialise/deserialise
TODO: OSCMap getters
    state analysers -> OSC senders
    iipyper osc returns?
TODO: tidy up `osc_receive_randomise`, move into iipyper.map.py?
TODO: IML: add default mapping?
TODO: Sardine: pattern utils?
TODO: @ti.func struct methods - can these be monkey patched?
    if not add to constructor as a dict
    use case would be Particles.Particle
'''

from typing import Any
from taichi._lib.core.taichi_python import DataType
import taichi as ti
import numpy as np
import jsons

from .npndarray_dict import NpNdarrayDict, np_vec2, np_vec3, np_vec4, TiNpTypeMap
from .utils import *

class StateDict(dotdict):
    def __init__(self, tolvera) -> None:
        self.tv = tolvera
        self.size = 0
    def set(self, name, kwargs: Any) -> None:
        if name in self and name != 'size':
            raise ValueError(f"[tolvera.state.StateDict] '{name}' already in dict.")
        try:
            self.add(name, kwargs)
        except TypeError as e:
            print(f"[tolvera.state.StateDict] TypeError setting {name}: {e}")
            raise
        except ValueError as e:
            print(f"[tolvera.state.StateDict] ValueError setting {name}: {e}")
            raise
        except Exception as e:
            print(f"[tolvera.state.StateDict] UnexpectedError setting {name}: {e}")
            raise
    def add(self, name, kwargs: Any):
        if name == 'tv' and type(kwargs) is not dict and type(kwargs) is not tuple:
            self[name] = kwargs
        elif name == 'size' and type(kwargs) is int:
            self[name] = kwargs
        elif type(kwargs) is dict:
            self[name] = State(self.tv, name=name, **kwargs)
            self.size += self[name].size
        elif type(kwargs) is tuple:
            self[name] = State(self.tv, name, *kwargs)
            self.size += self[name].size
        else:
            raise TypeError(f"[tolvera.state.StateDict] set() requires dict|tuple, not {type(kwargs)}")
    def from_vec(self, states: list[str], vector: list[float]):
        sizes_sum = self.get_size(states)
        assert sizes_sum == len(vector), f"sizes_sum={sizes_sum} != len(vector)={len(vector)}"
        vec_start = 0
        for state in states:
            s = self.tv.s[state]
            vec = vector[vec_start:vec_start+s.size]
            s.from_vec(vec)
            vec_start += s.size
    def get_size(self, states: str|list[str]) -> int:
        if isinstance(states, str): states = [states]
        return sum([self.tv.s[state].size for state in states])
    def __setattr__(self, __name: str, __value: Any) -> None:
        self.set(__name, __value)

@ti.data_oriented
class State:
    def __init__(self, 
                 tolvera,
                 name: str,
                 state: dict[str, tuple[DataType, Any, Any]],
                 shape: int|tuple[int] = None,
                 iml: str|tuple = None, # 'get' | ('get', 'set')
                 osc: str|tuple = None, # 'get' | ('get', 'set')
                 randomise: bool = True,
                 methods: dict[str, Any] = None):
        self.tv = tolvera
        assert name is not None, "State must have a name."
        self.name = name
        shape = 1 if shape is None else shape
        self.setup_data(state, shape, randomise, methods)
        self.setup_accessors(iml, osc)

    def setup_data(self, dict: dict[str, tuple[DataType, Any, Any]], shape: int|tuple[int], randomise: bool = True, methods: dict[str, Any] = None):
        self.create_struct_field(dict, shape, methods)
        self.create_npndarray_dict()
        if randomise: self.randomise()

    def create_struct_field(self, dict: dict[str, tuple[DataType, Any, Any]], shape: int|tuple[int], methods: dict[str, Any] = None):
        self.dict = dict
        self.shape = (shape,) if isinstance(shape, int) else shape
        if methods is None:
            self.struct = ti.types.struct(**{k: v[0] for k, v in self.dict.items()})
        else:
            self.methods = methods if methods is not None else {}
            self.struct = ti.types.struct(**{k: v[0] for k, v in self.dict.items()}, methods=self.methods)
        self.field = self.struct.field(shape=self.shape)

    def create_npndarray_dict(self):
        nddict = {}
        for k, v in self.dict.items():
            titype, min_val, max_val = v
            nptype = TiNpTypeMap.get(titype)
            if nptype is None:
                raise NotImplementedError(f"no nptype for {titype}")
            nddict[k] = (nptype, min_val, max_val)
        self.nddict = NpNdarrayDict(nddict, self.shape)
        self.size = self.nddict.size

    def randomise(self):
        self.nddict.randomise()
        self.from_nddict()
    
    def setup_accessors(self, iml: tuple=None, osc: tuple=None):
        self.setter_name = f"{self.tv.name_clean}_set_{self.name}"
        self.getter_name = f"{self.tv.name_clean}_get_{self.name}"
        self.handle_accessor_flags(iml, osc)
        if self.tv.iml is not False and self.iml:
            self.setup_iml_mapping()
        if self.tv.osc is not False and self.osc:
            self.setup_osc_mapping()

    def handle_accessor_flags(self, iml, osc):
        self.iml, self.iml_get, self.iml_set = self.handle_get_set(iml)
        self.osc, self.osc_get, self.osc_set = self.handle_get_set(osc)

    def handle_get_set(self, flag):
        enabled = flag is not None
        if isinstance(flag, str): flag = (flag,)
        get = 'get' in flag if enabled else False
        set = 'set' in flag if enabled else False
        return enabled, get, set

    def setup_iml_mapping(self):
        self.iml = self.tv.iml
        if self.iml_set:
            self.add_iml_setters()
        if self.iml_get:
            self.add_iml_getters()
    
    def add_iml_setters(self):
        name = self.setter_name
        """
        self.iml[name] = IMLOSCToFunc(self.tv)
        """
        self.iml.add_instance(name+'')

    def add_iml_getters(self):
        name = self.getter_name
        """
        self.iml[name] = IMLFuncToOSC(self.tv)
        """
        self.iml.add_instance(name+'')

    def setup_osc_mapping(self):
        self.osc = self.tv.osc
        if self.osc_set:
            self.add_osc_setters()
            if self.iml_set:
                self.add_iml_osc_setters()
        if self.osc_get:
            self.add_osc_getters()
            if self.iml_get:
                self.add_iml_osc_getters()

    def add_osc_setters(self):
        name = self.setter_name
        # randomise
        self.osc.map.receive_args_inline(name+'_randomise', self._randomise)
        # state
        f = self.osc.map.receive_list_with_idx
        f(f"{name}_idx", self.set_state_idx_from_list, 2, getattr(self,'len_state_idx'))
        f(f"{name}_row", self.set_state_row_from_list, 1, getattr(self,'len_state_row'))
        f(f"{name}_col", self.set_state_col_from_list, 1, getattr(self,'len_state_col'))
        f(f"{name}_all", self.set_state_all_from_list, 0, getattr(self,'len_state_all'))
        # state attributes
        for k,v in self.dict.items():
            f(f"{name}_{k}_idx", self.set_attr_idx, 2, 1, k)
            f(f"{name}_{k}_row", self.set_attr_row, 1, getattr(self,'len_attr_row'), k)
            f(f"{name}_{k}_col", self.set_attr_col, 1, getattr(self,'len_attr_col'), k)
            f(f"{name}_{k}_all", self.set_attr_all, 0, getattr(self,'len_attr_all'), k)

    def add_osc_getters(self):
        name = self.getter_name
        for k,v in self.dict.items():
            ranges = (int(v[0]), int(v[0]), int(v[1]))
            kwargs = {'i': ranges, 'j': ranges, 'attr': (k,k,k)}
            self.osc.map.receive_args_inline(f"{name}", self.osc_getter, **kwargs)

    def osc_getter(self, i: int, j: int, attribute: str):
        ret = self.get((i,j), attribute)
        if ret is not None:
            route = self.osc.map.pascal_to_path(self.getter_name)#+'/'+attribute
            self.osc.host.return_to_sender_by_name((route, attribute,ret), self.osc.client_name)
        return ret

    '''
    def add_osc_streams(self, name):
        add in broadcast mode
        pass
    '''

    def add_iml_osc_setters(self):
        name = self.setter_name

    def add_iml_osc_getters(self):
        name = self.getter_name

    def serialize(self) -> str:
        return ti_serialize(self.field)
    
    def deserialize(self, json_str: str):
        ti_deserialize(self.field, json_str)

    def save(self, path: str):
        # TODO: path validation, save to path, etc.
        json_str = self.serialize()
    
    def load(self, path: str):
        # TODO: path validation, file ext., etc.
        # TODO: data validation (pydantic?)
        json_str = jsons.load(path)
        self.deserialize(json_str)

    def from_nddict(self):
        try:
            data = self.nddict.get_data()
            self.field.from_numpy(data)
        except TypeError as e:
            print(f"[tolvera.state.from_nddict] TypeError: {e}")
            raise
        except ValueError as e:
            print(f"[tolvera.state.from_nddict] ValueError: {e}")
            raise
        except Exception as e:
            print(f"[tolvera.state.from_nddict] UnexpectedError: {e}")
            raise

    def to_nddict(self):
        try:
            data = self.field.to_numpy()
            self.nddict.set_data(data)
        except TypeError as e:
            print(f"[tolvera.state.to_nddict] TypeError: {e}")
            raise
        except ValueError as e:
            print(f"[tolvera.state.to_nddict] ValueError: {e}")
            raise
        except Exception as e:
            print(f"[tolvera.state.to_nddict] UnexpectedError: {e}")
            raise

    """
    npndarray_dict wrappers
    """
    
    def from_vec(self, vec: list):
        self.to_nddict()
        self.nddict.from_vec(vec)
        self.from_nddict()
    
    def to_vec(self) -> list:
        self.to_nddict()
        return self.nddict.to_vec()
    
    def attr_from_vec(self, attr:str, vec: list):
        self.to_nddict()
        self.nddict.attr_from_vec(attr, vec)
        self.from_nddict()
    
    def attr_to_vec(self, attr:str) -> list:
        self.to_nddict()
        return self.nddict.attr_to_vec(attr)
    
    def slice_from_vec(self, slice_args:list, slice_vec: list):
        self.to_nddict()
        self.nddict.slice_from_vec(slice_args, slice_vec)
        self.from_nddict()
    
    def slice_to_vec(self, slice_args:list) -> list:
        self.to_nddict()
        return self.nddict.slice_to_vec(slice_args)
    
    def attr_slice_from_vec(self, attr:str, slice_args:list, slice_vec: list):
        self.to_nddict()
        self.nddict.attr_slice_from_vec(attr, slice_args, slice_vec)
        self.from_nddict()
    
    def attr_slice_to_vec(self, attr:str, slice_args:list) -> list:
        self.to_nddict()
        return self.nddict.attr_slice_to_vec(attr, slice_args)
    
    def attr_size(self, attr:str) -> int:
        return self.nddict.data[attr].size

    @ti.func
    def __getitem__(self, key):
        return self.field[key]

    def __call__(self, *args: Any, **kwds: Any) -> Any:
        return self.field
