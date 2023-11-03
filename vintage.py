from __future__ import annotations

from dataclasses import dataclass, replace
import math
import random
from typing import Any, Callable, Generic, Iterable, Tuple, TypeVar, Union
from example import Person, sort_by_age, wrong_sort_by_age, is_valid

T = TypeVar("Value", covariant=True)
T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V")


class Generator(Generic[T]):
    def __init__(self, generate: Callable[[], T]):
        self._generate = generate

    def generate(self) -> T:
        return self._generate()


def sample(gen: Generator[T]) -> list[T]:
    return [gen.generate() for _ in range(3)]


def always(value: T) -> Generator[T]:
    return Generator(lambda: value)


pie = always(math.pi)

pure = always


def int_between(low: int, high: int) -> Generator[int]:
    return Generator(lambda: random.randint(low, high))


age = int_between(0, 100)


def map(f: Callable[[T], U], gen: Generator[T]) -> Generator[U]:
    return Generator(lambda: f(gen.generate()))


letter = map(chr, int_between(ord('a'), ord('z')))


def mapN(f: Callable[..., T],
         gens: Iterable[Generator[Any]]) -> Generator[T]:
    return Generator(lambda: f(*[gen.generate() for gen in gens]))


def list_of_length(n: int, gen: Generator[T]) -> Generator[list[T]]:
    "n is the length of the lists"
    return mapN(lambda *args: list(args), [gen] * n)


simple_name = map("".join, list_of_length(6, letter))
person = mapN(Person, (simple_name, age))


def bind(f: Callable[[T], Generator[U]], gen: Generator[T]) -> Generator[U]:
    return Generator(lambda: f(gen.generate()).generate())


def list_of_random_length(gen: Generator[T]) -> Generator[list[T]]:
    length = int_between(0, 10)
    return bind(lambda length: list_of_length(length, gen), length)


def bindN(f: Callable[..., Generator[T]],
          gens: Iterable[Generator[Any]]) -> Generator[T]:
    return Generator(lambda: f(*[gen.generate() for gen in gens]).generate())


list_of_person = list_of_length(2, person)
list_of_person_random_length = list_of_random_length(person)


def choice(from_gens: Iterable[Generator[T]]) -> Generator[T]:
    all = tuple(from_gens)
    which_gen = int_between(0, len(all)-1)
    return bind(lambda i: all[i], which_gen)


# A property is just a generator of booleans. The idea is we generate the bool
# from this 100 times, or until it generates False, at which point we fail the
# test.
Property1 = Generator[bool]


def for_all_1(gen: Generator[T], property: Callable[[T], bool]) -> Property1:
    return map(property, gen)


rev_of_rev_1 = for_all_1(list_of_random_length(letter), lambda lst: list(
    reversed(list(reversed(lst)))) == lst)

sort_by_age_1 = for_all_1(list_of_person_random_length,
                          lambda persons: is_valid(persons,
                                                   sort_by_age(persons)))

wrong_sort_by_age_1 = for_all_1(list_of_person_random_length,
                                lambda persons: is_valid(
                                    persons,
                                    wrong_sort_by_age(persons)))


def test_1(property: Property1):
    for test_number in range(100):
        if not property.generate():
            print(f"Fail: at test {test_number}.")
            return
    print("Success: 100 tests passed.")

# what if we want to write for_all over multiple arguments?
# e.g. if I add an integer to each element of a list, then its sum will change
# by (length of the list) * (integer) this doesn't work without a slightly
# smarter for_all


def for_all_2(gen: Generator[T],
              property: Callable[[T], Union[Property1, bool]]) -> Property1:
    def property_wrapper(value: T) -> Property1:
        outcome = property(value)
        if isinstance(outcome, bool):
            return pure(outcome)  # innermost for_all_2
        else:
            return outcome  # one of the outer for_all_2
    return bind(property_wrapper, gen)


sum_of_list_2 = for_all_2(
    list_of_random_length(int_between(-10, 10)),
    lambda lst: for_all_2(
        int_between(-10, 10),
        lambda i: sum(e+i for e in lst) == sum(lst) + len(lst) * i))

# now we might think this would be better/more pythonic variant with variadic
# args - but this is slightly less powerful - for_all is really like bind,
# while for_allN is like mapN. For example, with for_all you can generate
# a random value and then make any of the inner generators depend on that
# value.


def for_allN(gens: Iterable[Generator[Any]],
             property: Callable[..., Union[bool, Property1]]) -> Property1:
    ...


# doesn't make a lot of sense but impossible to write with for_allN
weird_sum_of_list = for_all_2(
    int_between(-10, 10),
    lambda i: for_all_2(
        list_of_random_length(always(i)),
        lambda lst: sum(e+i for e in lst) == sum(lst) + len(lst) * i))

wrong_2 = for_all_2(list_of_random_length(letter),
                    lambda lst: list(reversed(lst)) == lst)

# ok, but let's try to make it print on which values it failed - this needs a
# change to for_all, and the type of property.


@dataclass(frozen=True)
class TestResult:
    is_success: bool
    arguments: Tuple[Any, ...]


Property = Generator[TestResult]


def for_all(gen: Generator[T],
            property: Callable[[T], Union[Property, bool]]) -> Property:
    def property_wrapper(value: T) -> Property:
        outcome = property(value)
        if isinstance(outcome, bool):
            return always(TestResult(is_success=outcome, arguments=(value,)))
        else:
            return map(
                lambda inner_out: replace(
                    inner_out,
                    arguments=(value,) + inner_out.arguments),
                outcome)
    return bind(property_wrapper, gen)


def test(property: Property):
    for test_number in range(100):
        result = property.generate()
        if not result.is_success:
            print(f"Fail: at test {test_number} with arguments {
                  result.arguments}.")
            return
    print("Success: 100 tests passed.")


wrong = for_all(list_of_random_length(letter),
                lambda lst: list(reversed(lst)) == lst)

rev_of_rev = for_all(list_of_random_length(
    letter), lambda lst: list(reversed(list(reversed(lst)))) == lst)

sum_of_list = for_all(
    list_of_random_length(int_between(-10, 10)),
    lambda lst:
    for_all(int_between(-10, 10),
            lambda i:
            sum(e+i for e in lst) == sum(lst) + len(lst) * i))

prop_sort_by_age = for_all(list_of_person_random_length,
                           lambda persons_in:
                           is_valid(persons_in, sort_by_age(persons_in)))

prop_wrong_sort_by_age = for_all(list_of_person_random_length,
                                 lambda persons_in:
                                 is_valid(persons_in,
                                          wrong_sort_by_age(persons_in)))

prop_weird_shrink = for_all(
    int_between(-20, -1),
    lambda i: i * i < 0)
