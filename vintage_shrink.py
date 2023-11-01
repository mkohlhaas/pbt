from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Protocol, TypeVar

from example import (Person, wrong_sort_by_age, is_valid)
from vintage import (Generator, TestResult, int_between,
                     list_of_random_length, list_of_person, map)


T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")


class Shrink(Protocol[T]):
    def __call__(self, value: T) -> Iterable[T]:
        ...


def shrink_int(value: int) -> Iterable[int]:
    if value != 0:
        yield 0
    current = abs(value) // 2
    while current != 0:
        yield abs(value) - current
        current = current // 2


def shrink_letter(value: str) -> Iterable[str]:
    for candidate in ('a', 'b', 'c'):
        if candidate < value:
            yield candidate


def shrink_list(value: list[T], shrink_elem: Shrink[T]) -> Iterable[list[T]]:
    length = len(value)
    if length > 0:
        yield []
        half_length = length // 2
        while half_length != 0:
            yield value[:half_length]
            yield value[half_length:]
            half_length = half_length // 2
        for i, elem in enumerate(value):
            for smaller_elem in shrink_elem(elem):
                smaller_list = list(value)
                smaller_list[i] = smaller_elem
                yield smaller_list


@dataclass(frozen=True)
class CandidateTree(Generic[T]):
    value: T
    candidates: Iterable[CandidateTree[T]]

    def __str__(self, level=0):
        ret = "\t"*level+repr(self.value)+"\n"
        for candidate in self.candidates:
            ret += candidate.__str__(level+1)
        return ret

    def __repr__(self):
        return '<tree node representation>'


def tree_from_shrink(value: T, shrink: Shrink[T]) -> CandidateTree[T]:
    return CandidateTree(
        value=value,
        # due to the way python iterators work, this can only be evaluated
        # once. But that's OK for our purposes.
        candidates=(tree_from_shrink(v, shrink) for v in shrink(value))
    )


def tree_map(f: Callable[[T], U], tree: CandidateTree[T]) -> CandidateTree[U]:
    u = f(tree.value)
    branches_u = (tree_map(f, branch) for branch in tree.candidates)
    return CandidateTree(value=u, candidates=branches_u)


Property = Generator[CandidateTree[TestResult]]


def for_all(gen: Generator[T],
            shrink: Shrink[T],
            property: Callable[[T], bool]) -> Property:
    def property_wrapper(value: T) -> CandidateTree[TestResult]:
        search_tree = tree_from_shrink(value, shrink)
        search_tree_test = tree_map(
            lambda v: TestResult(is_success=property(v), arguments=(v,)),
            search_tree
        )
        return search_tree_test

    return map(property_wrapper, gen)


def test(property: Property):
    def do_shrink(tree: CandidateTree[TestResult]) -> None:
        for smaller in tree.candidates:
            if not smaller.value.is_success:
                # cool, found a smaller value that still fails - keep shrinking
                print(f"Shrinking: found smaller arguments {
                      smaller.value.arguments}")
                do_shrink(smaller)
                return
        print(f"Shrinking: giving up - smallest arguments found {
              tree.value.arguments}")

    for test_number in range(100):
        result = property.generate()
        if not result.value.is_success:
            print(f"Fail: at test {test_number} with arguments {
                  result.value.arguments}.")
            do_shrink(result)
            return
    print("Success: 100 tests passed.")


wrong_shrink_1 = for_all(
    int_between(0, 20),
    shrink_int,
    lambda i: i <= 3
)


wrong_shrink_2 = for_all(
    list_of_random_length(int_between(0, 10)),
    lambda lst1: shrink_list(lst1, shrink_int),
    lambda lst2: list(reversed(lst2)) == lst2
)


def shrink_name(name: str) -> Iterable[str]:
    name_as_list = list(name)
    for smaller_list in shrink_list(name_as_list, shrink_letter):
        yield "".join(smaller_list)


def shrink_person(value: Person) -> Iterable[Person]:
    for smaller_age in shrink_int(value.age):
        yield Person(value.name, smaller_age)
    for smaller_name in shrink_name(value.name):
        yield Person(smaller_name, value.age)


def shrink_list_of_person(value: list[Person]) -> Iterable[list[Person]]:
    return shrink_list(value, shrink_person)


prop_wrong_sort_by_age = for_all(
    list_of_person, shrink_list_of_person,
    lambda persons_in: is_valid(persons_in, wrong_sort_by_age(persons_in)))
