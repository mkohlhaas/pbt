# Everything now is in terms of CandidateTree Generators instead
# of simple Generators which leads to unification of generation and shrinking.

# compare map, mapN, bind, ... with vintage.py's versions
# also age, letter, ...

# no explicit shrink_list, built into the CandidateTree
# see function tree_mapN

from __future__ import annotations
from copy import copy

from dataclasses import dataclass, replace
import itertools
import random
from typing import Any, Callable, Generic, Iterable, Protocol, TypeVar, Union

from example import Person, is_valid, sort_by_age, wrong_sort_by_age

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")

# Generators ####################################################


class Generator(Generic[T]):
    def __init__(self, generator: Callable[[], T]):
        self._generator = generator

    def generate(self) -> T:
        return self._generator()


def gen_sample(gen: Generator[T]) -> list[T]:
    return [gen.generate() for _ in range(10)]


def gen_constant(value: T) -> Generator[T]:
    return Generator(lambda: value)


pure = gen_constant


def gen_int_between(low: int, high: int) -> Generator[int]:
    return Generator(lambda: random.randint(low, high))


def gen_map(f: Callable[[T], U], gen: Generator[T]) -> Generator[U]:
    return Generator(lambda: f(gen.generate()))


def gen_mapN(f: Callable[..., T],
             gens: Iterable[Generator[Any]]) -> Generator[T]:
    return Generator(lambda: f(gen.generate() for gen in gens))


def gen_bind(func: Callable[[T], Generator[U]],
             gen: Generator[T]) -> Generator[U]:
    return Generator(func(gen.generate()).generate)


# Shrinkers ######################################################

class Shrink(Protocol[T]):
    def __call__(self, value: T) -> Iterable[T]:
        ...


def shrink_int(low: int, high: int) -> Shrink[int]:
    target = 0
    if low > 0:
        target = low
    if high < 0:
        target = high

    def shrinker(value: int) -> Iterable[int]:
        if value == target:
            return
        half = (value - target) // 2
        current = value - half
        while half != 0 and current != target:
            yield current
            half = (current - target) // 2
            current = current - half
        yield target
    return shrinker


# Candidates #####################################################

class CandidateTree(Generic[T]):

    def __init__(self, value: T,
                 candidates: Iterable[CandidateTree[T]]) -> None:
        self._value = value
        # return a cached iterator
        (self._candidates,) = itertools.tee(candidates, 1)

    @property
    def value(self):
        return self._value

    @property
    def candidates(self):
        # reset the iterator to the start
        return copy(self._candidates)

    def __str__(self, level=0):
        ret = "\t"*level+repr(self.value)+"\n"
        for candidate in self.candidates:
            ret += candidate.__str__(level+1)
        return ret

    def __repr__(self):
        return '<tree node representation>'

# instead of randomly generating values T we are generating entire trees of T


def tree_constant(value: T) -> CandidateTree[T]:
    return CandidateTree(value, tuple())


def tree_from_shrink(value: T, shrink: Shrink[T]) -> CandidateTree[T]:
    return CandidateTree(
        value=value,
        candidates=(
            tree_from_shrink(v, shrink)
            for v in shrink(value)
        )
    )


def tree_map(f: Callable[[T], U], tree: CandidateTree[T]) -> CandidateTree[U]:
    return CandidateTree(
        value=f(tree.value),
        candidates=(tree_map(f, candidate) for candidate in tree.candidates)
    )


def tree_map2(f: Callable[[T, U], V],
              tree_1: CandidateTree[T],
              tree_2: CandidateTree[U],
              ) -> CandidateTree[V]:

    value = f(tree_1.value, tree_2.value)

    candidates_1 = (
        tree_map2(f, candidate, tree_2) for candidate in tree_1.candidates
    )

    candidates_2 = (
        tree_map2(f, tree_1, candidate) for candidate in tree_2.candidates
    )

    return CandidateTree(
        value=value,
        candidates=itertools.chain(
            candidates_1,
            candidates_2
        )
    )


tree_1 = tree_from_shrink(1, shrink_int(0, 10))
tree_2 = tree_from_shrink(3, shrink_int(0, 10))
tree_tuples = tree_map2(lambda x, y: (x, y), tree_1, tree_2)


def tree_mapN(f: Callable[..., U],
              trees: Iterable[CandidateTree[Any]]) -> CandidateTree[U]:
    trees = list(trees)
    value = f([tree.value for tree in trees])

    def _copy_and_set(trees: list[T], i: int, tree: T) -> list[T]:
        result = list(trees)
        result[i] = tree
        return result

    candidates = (
        tree_mapN(f, _copy_and_set(trees, i, candidate))
        for i in range(len(trees))
        for candidate in trees[i].candidates
    )

    return CandidateTree(
        value=value,
        candidates=candidates
    )


def tree_bind(f: Callable[[T], CandidateTree[U]],
              tree: CandidateTree[T]
              ) -> CandidateTree[U]:
    tree_u = f(tree.value)
    candidates = (
        tree_bind(f, candidate)
        for candidate in tree.candidates
    )

    return CandidateTree(
        value=tree_u.value,
        candidates=itertools.chain(
            candidates,
            tree_u.candidates
        )
    )


def letters(length: int):
    if length == 0:
        return tree_constant('')
    abc = tree_from_shrink(ord('c'), shrink_int(ord('a'), ord('c')))
    abc_repeat = tree_map(lambda o: chr(o) * length, abc)
    return abc_repeat


tree_list_length = tree_from_shrink(3, shrink_int(0, 3))
tree_bound = tree_bind(letters, tree_list_length)


# Candidate Generators ##########################################

CTGenerator = Generator[CandidateTree[T]]


def always(value: T) -> CTGenerator[T]:
    return gen_constant(tree_constant(value))


pure = always

constant = always


def int_between(low: int, high: int) -> CTGenerator[int]:
    return gen_map(lambda v: tree_from_shrink(v, shrink_int(low, high)),
                   gen_int_between(low, high))


def map(f: Callable[[T], U], gen: CTGenerator[T]) -> CTGenerator[U]:
    return gen_map(lambda tree: tree_map(f, tree), gen)


def mapN(f: Callable[..., T],
         gens: Iterable[CTGenerator[Any]]) -> CTGenerator[T]:
    return gen_mapN(lambda trees: tree_mapN(f, trees), gens)


def list_of_gen(gens: Iterable[CTGenerator[Any]]) -> CTGenerator[list[Any]]:
    return mapN(lambda args: list(args), gens)


def list_of_length(length: int, gen: CTGenerator[T]) -> CTGenerator[list[T]]:
    return list_of_gen([gen] * length)


def bind(f: Callable[[T], CTGenerator[U]],
         gen: CTGenerator[T]) -> CTGenerator[U]:
    def inner_bind(value: T) -> CandidateTree[U]:
        random_tree = f(value)
        return random_tree.generate()
    return gen_map(lambda tree: tree_bind(inner_bind, tree), gen)


def list_of(gen: CTGenerator[T]) -> CTGenerator[list[T]]:
    length = int_between(0, 10)
    return bind(lambda lst: list_of_length(lst, gen), length)


# Properties ####################################################

@dataclass(frozen=True)
class TestResult:
    is_success: bool
    arguments: tuple[Any, ...]


Property = CTGenerator[TestResult]


def for_all(gen: CTGenerator[T],
            property: Callable[[T], Union[Property, bool]]) -> Property:
    def property_wrapper(value: T) -> Property:
        outcome = property(value)
        if isinstance(outcome, bool):
            return always(TestResult(is_success=outcome, arguments=(value,)))
        else:
            return map(
                lambda inner_out:  # inner_out: TestResult
                replace(inner_out, arguments=(value,) + inner_out.arguments),
                outcome)
    return bind(property_wrapper, gen)


def test(property: Property):
    def do_shrink(tree: CandidateTree[TestResult]) -> None:
        for smaller in tree.candidates:
            if not smaller.value.is_success:
                print(f"Shrinking: found smaller arguments {
                      smaller.value.arguments}")
                do_shrink(smaller)
                break
        else:
            print(f"Shrinking: gave up at arguments {tree.value.arguments}")

    for test_number in range(100):
        result = property.generate()
        if not result.value.is_success:
            print(f"Fail: at test {test_number} with arguments {
                  result.value.arguments}.")
            do_shrink(result)
            return
    print("Success: 100 tests passed.")


wrong_sum = for_all(list_of(
    int_between(-10, 10)),
    lambda lst:
    for_all(int_between(-10, 10),
            lambda i:
            sum(e+i for e in lst) == sum(lst) + (len(lst) + 1) * i))

equality = for_all(int_between(-10, 10), lambda lst:
                   for_all(int_between(-10, 10), lambda i: lst == i))

age = int_between(0, 100)

letter = map(chr, int_between(ord('a'), ord('z')))

simple_name = map("".join, list_of_length(6, letter))

person = mapN(lambda a: Person(*a), (simple_name, age))

lists_of_person = list_of(person)

prop_sort_by_age = for_all(
    lists_of_person,
    lambda persons_in: is_valid(persons_in, sort_by_age(persons_in)))

prop_wrong_sort_by_age = for_all(
    lists_of_person,
    lambda persons_in: is_valid(persons_in, wrong_sort_by_age(persons_in)))

prop_weird_shrink = for_all(
    int_between(-20, -1),
    lambda i: i * i < 0)
