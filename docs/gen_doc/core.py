import math, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Collection, Callable, Union, Iterator, Tuple, NewType, List, Sequence, Dict
from functools import partial, reduce
from fast_progress import master_bar, progress_bar
from collections import defaultdict, abc, namedtuple, Iterable


FileLike = Union[str, Path]
Floats = Union[float, Collection[float]]
AnnealingFt = Union[Callable[[float,float,float],float],Callable[[float,float,float,float],float]]


class Parentclass():
    pass

class Subclass(Parentclass):
    def __init__(self, var: int = 10): pass

    def update(self): pass

    def remove(self): pass

    @classmethod
    def cmethod(x): pass

def example_function(x:int, cls:Parentclass=None) -> str:
    """
    Provides an example to how docstrings are resolved
    :param x: Number to store
    :param cls: Class string
    :return: Error string
    """
    pass

def linked_docstring_example(x:int, s:str='Hello') -> bool:
    """Should link to `example_function`"""
    pass

def is_tuple(x) -> bool:    return isinstance(x, tuple)
def is_listy(x) -> bool:    return isinstance(x, (tuple,list))
def is_iterable(x) -> bool: return isinstance(x, Iterable)

def listify(p=None, q=None) -> Collection:
    "Makes p a list that looks like q"
    if p is None: p=[]
    elif not is_iterable(p): p=[p]
    n = q if type(q)==int else 1 if q is None else len(q)
    if len(p)==1: p = p * n
    return p

class SmoothenValue():
    "To compute the moving average of values"

    def __init__(self, beta:float):
        self.beta,self.n,self.mov_avg = beta,0,0

    def __repr__(self) -> str:
        return f'SmoothenValue: current {self.smooth}, n={self.n}'

    def add_value(self, val:float):
        self.n += 1
        self.mov_avg = self.beta * self.mov_avg + (1 - self.beta) * val
        self.smooth = self.mov_avg / (1 - self.beta ** self.n)

def annealing_no(start:float, end:float, pct:float) -> float:     return start
def annealing_linear(start:float, end:float, pct:float) -> float: return start + pct * (end-start)
def annealing_exp(start:float, end:float, pct:float) -> float:    return start * (end/start) ** pct
def annealing_cos(start:float, end:float, pct:float) -> float:
    cos_out = np.cos(np.pi * pct) + 1
    return end + (start-end)/2 * cos_out

def do_annealing_poly(start:float, end:float, pct:float, degree:float) -> float:
    return end + (start-end) * (1-pct)**degree
def annealing_poly(degree:float) -> Callable: return partial(do_annealing_poly, degree=degree)

