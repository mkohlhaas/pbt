from __future__ import annotations

from dataclasses import dataclass, replace
import random
from typing import (Any, Callable, Generic, Iterable,
                    Optional, Tuple, TypeVar, Union)
from example import Person, is_valid, sort_by_age, wrong_sort_by_age

T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")

Size = int


class SizeExceeded(Exception):
    pass


class Generator(Generic[T]):
    def __init__(self,
                 generator: Callable[[Optional[Size]], Tuple[T, Size]]):
        self._generator = generator

    def generate(self, min_size: Optional[Size] = None) -> Tuple[T, Size]:
        return self._generator(min_size)


def sample(gen: Generator[T]) -> list[T]:
    return [gen.generate()[0] for _ in range(10)]


def always(value: T) -> Generator[T]:
    return Generator(lambda _: (value, 0))


constant = always
pure = always


def decrease_size(min_size: Optional[Size], decrease: Size) -> Optional[Size]:
    if min_size is None:
        return None
    smaller = min_size-decrease
    if smaller < 0:
        raise SizeExceeded(f"{min_size=} {decrease=} {smaller=}")
    return smaller


def int_between(low: int, high: int) -> Generator[int]:
    def zig_zag(i: int):
        if i < 0:
            return -2*i - 1
        else:
            return 2*i

    def generator(min_size: Optional[Size]):
        value = random.randint(low, high)
        size = zig_zag(value)
        decrease_size(min_size, size)
        return value, size
    return Generator(generator)


def map(f: Callable[[T], U], gen: Generator[T]) -> Generator[U]:
    def generator(min_size: Optional[Size]):
        result, size = gen.generate(min_size)
        return f(result), size
    return Generator(generator)


def mapN(f: Callable[..., T],
         gens: Iterable[Generator[Any]]) -> Generator[T]:
    def generator(min_size: Optional[Size]):
        results: list[Any] = []
        size_acc = 0
        for gen in gens:
            result, size = gen.generate(min_size)
            min_size = decrease_size(min_size, size)
            results.append(result)
            size_acc += size
        return f(*results), size_acc
    return Generator(generator)


def bind(f: Callable[[T], Generator[U]], gen: Generator[T]) -> Generator[U]:
    def generator(min_size: Optional[Size]):
        result, size_outer = gen.generate(min_size)
        min_size = decrease_size(min_size, size_outer)
        result, size_inner = f(result).generate(min_size)
        size = size_inner+size_outer
        return result, size
    return Generator(generator)


Gen = Generator[T]


@dataclass(frozen=True)
class TestResult:
    is_success: bool
    arguments: Tuple[Any, ...]


Property = Gen[TestResult]


def for_all(gen: Gen[T],
            property: Callable[[T], Union[Property, bool]]) -> Property:
    def property_wrapper(value: T) -> Property:
        outcome = property(value)
        if isinstance(outcome, bool):
            return always(TestResult(is_success=outcome, arguments=(value,)))
        else:
            return map(
                lambda inner_out:
                replace(inner_out,
                        arguments=(value,) + inner_out.arguments), outcome)
    return bind(property_wrapper, gen)


def test(property: Property):
    def find_smaller(min_result: TestResult, min_size: Size):
        skipped, not_shrunk, shrunk = 0, 0, 0
        while skipped + not_shrunk + shrunk <= 100_000 and min_size > 0:
            try:
                result, size = property.generate(min_size)
                if size >= min_size:
                    skipped += 1
                elif not result.is_success:
                    shrunk += 1
                    min_result, min_size = result, size
                    print(f"Shrinking: found smaller arguments {
                        result.arguments}")
                else:
                    not_shrunk += 1
                    print(f"Shrinking: didn't work, smaller arguments {
                        result.arguments} passed the test")
            except SizeExceeded:
                skipped += 1

        print(f"Shrinking: gave up at arguments {min_result.arguments}")
        print(f"{skipped=} {not_shrunk=} {shrunk=} {min_size=}")

    for test_number in range(100):
        result, size = property.generate()
        if not result.is_success:
            print(f"Fail: at test {test_number} with arguments {
                  result.arguments}.")
            find_smaller(result, size)
            return
    print("Success: 100 tests passed.")


# we don't even have to change the definition of letters!
letter = map(chr, int_between(ord('a'), ord('z')))


def list_of_gen(gens: Iterable[Gen[Any]]) -> Gen[list[Any]]:
    return mapN(lambda *args: list(args), gens)


def list_of_length(n: int, gen: Gen[T]) -> Gen[list[T]]:
    gen_of_list = list_of_gen([gen] * n)
    return gen_of_list


def list_of(gen: Gen[T]) -> Gen[list[T]]:
    length = int_between(0, 10)
    return bind(lambda n: list_of_length(n, gen), length)


wrong_sum = for_all(list_of(int_between(-10, 10)), lambda lst:
                    for_all(int_between(-10, 10), lambda i:
                    sum(e+i for e in lst) == sum(lst) + (len(lst) + 1) * i))

equality = for_all(int_between(-10, 10), lambda n:
                   for_all(int_between(-10, 10), lambda i: n == i))

equality_letters = (
    for_all(letter, lambda n:
            for_all(letter, lambda i: n == i))
)

age = int_between(0, 100)

letter = map(chr, int_between(ord('a'), ord('z')))

simple_name = map("".join, list_of_length(6, letter))

person = mapN(Person, (simple_name, age))

lists_of_person = list_of(person)

prop_sort_by_age = for_all(
    lists_of_person,
    lambda persons_in: is_valid(persons_in, sort_by_age(persons_in)))

prop_wrong_sort_by_age = for_all(
    lists_of_person,
    lambda persons_in: is_valid(persons_in, wrong_sort_by_age(persons_in)))
