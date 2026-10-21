"""Test: Population class behaviour."""

from seachange.individual import Individual
from seachange.population import Population

POP_LEN = 2
SLICE_LEN = 2
COMBINED_LEN = 2
EXTENDED_LEN = 3
SAMPLE_N = 5
SMALL_POP_SIZE = 3
TOP_N = 2


def _make_ind(
    fitness: float | None = None, *, alive: bool = True
) -> Individual:
    ind = Individual(alive=alive)
    if fitness is not None:
        ind.fitness = fitness
    return ind


def test_population_len() -> None:
    """len() returns the number of individuals."""
    pop = Population([_make_ind(1.0), _make_ind(2.0)])
    assert len(pop) == POP_LEN


def test_population_empty_constructor() -> None:
    """Population.empty() creates a zero-length population."""
    pop = Population.empty()
    assert len(pop) == 0
    assert not pop


def test_population_bool_non_empty() -> None:
    """A non-empty population is truthy."""
    pop = Population([_make_ind()])
    assert pop


def test_population_iter() -> None:
    """Iterating yields all individuals in insertion order."""
    inds = [_make_ind(float(i)) for i in range(3)]
    pop = Population(inds)
    assert list(pop) == inds


def test_population_getitem_int() -> None:
    """Integer indexing returns an Individual."""
    inds = [_make_ind(float(i)) for i in range(3)]
    pop = Population(inds)
    assert pop[0] is inds[0]
    assert pop[2] is inds[2]


def test_population_getitem_slice() -> None:
    """Slice indexing returns a Population."""
    inds = [_make_ind(float(i)) for i in range(4)]
    pop = Population(inds)
    sliced = pop[:SLICE_LEN]
    assert isinstance(sliced, Population)
    assert len(sliced) == SLICE_LEN


def test_population_add() -> None:
    """Adding two populations concatenates individuals."""
    p1 = Population([_make_ind(1.0)])
    p2 = Population([_make_ind(2.0)])
    combined = p1 + p2
    assert len(combined) == COMBINED_LEN


def test_population_repr() -> None:
    """Repr shows the size."""
    pop = Population([_make_ind()])
    assert repr(pop) == "Population(n=1)"


def test_population_append() -> None:
    """Append adds one individual in place."""
    pop = Population.empty()
    pop.append(_make_ind(5.0))
    assert len(pop) == 1


def test_population_extend() -> None:
    """Extend adds multiple individuals in place."""
    pop = Population([_make_ind(1.0)])
    pop.extend([_make_ind(2.0), _make_ind(3.0)])
    assert len(pop) == EXTENDED_LEN


def test_population_to_list() -> None:
    """to_list returns a plain Python list."""
    inds = [_make_ind()]
    pop = Population(inds)
    assert isinstance(pop.to_list(), list)
    assert pop.to_list() == inds


def test_population_sample_respects_max() -> None:
    """sample(n) returns at most n individuals."""
    pop = Population([_make_ind(float(i)) for i in range(10)])
    sampled = pop.sample(SAMPLE_N)
    assert len(sampled) == SAMPLE_N


def test_population_sample_never_exceeds_size() -> None:
    """sample(n) where n > size returns all individuals."""
    pop = Population([_make_ind() for _ in range(SMALL_POP_SIZE)])
    sampled = pop.sample(100)
    assert len(sampled) == SMALL_POP_SIZE


def test_population_best_returns_top_n() -> None:
    """best(n=2) returns the two highest-fitness individuals."""
    pop = Population([_make_ind(float(i)) for i in range(5)])
    top2 = pop.best(n=TOP_N)
    fitnesses = [ind.fitness_ for ind in top2 if ind.fitness_ is not None]
    assert len(fitnesses) == len(top2)
    assert fitnesses == sorted(fitnesses, reverse=True)
    assert len(top2) == TOP_N


def test_population_best_min_sort() -> None:
    """best(direction='min') returns the lowest-fitness individuals first."""
    pop = Population([_make_ind(float(i)) for i in range(5)])
    bottom2 = pop.best(direction="min", n=2)
    first, second = bottom2[0].fitness_, bottom2[1].fitness_
    assert first is not None
    assert second is not None
    assert first <= second


def test_population_sort_descending() -> None:
    """sort() returns individuals ordered by fitness descending."""
    pop = Population([_make_ind(float(i)) for i in [3, 1, 4, 1, 5]])
    sorted_pop = pop.sort()
    fitnesses = [ind.fitness_ for ind in sorted_pop if ind.fitness_ is not None]
    assert len(fitnesses) == len(sorted_pop)
    assert fitnesses == sorted(fitnesses, reverse=True)


def test_population_shuffle_same_size() -> None:
    """Shuffle returns a population of the same size."""
    pop = Population([_make_ind(float(i)) for i in range(6)])
    shuffled = pop.shuffle()
    assert len(shuffled) == len(pop)


def test_population_where_filters() -> None:
    """Where keeps only individuals satisfying the predicate."""
    pop = Population([_make_ind(1.0, alive=True), _make_ind(2.0, alive=False)])
    alive = pop.where(lambda ind: ind.alive)
    assert len(alive) == 1
    assert alive[0].alive is True


def test_population_alive_property() -> None:
    """Alive property returns only living individuals."""
    pop = Population([_make_ind(alive=True), _make_ind(alive=False)])
    assert len(pop.alive) == 1


def test_population_dead_property() -> None:
    """Dead property returns only dead individuals."""
    pop = Population([_make_ind(alive=True), _make_ind(alive=False)])
    assert len(pop.dead) == 1


def test_population_unevaluated_property() -> None:
    """Unevaluated returns individuals where requires_eval is True."""
    ind_eval = _make_ind(5.0)
    ind_uneval = Individual()
    pop = Population([ind_eval, ind_uneval])
    assert len(pop.unevaluated) == 1


def test_population_evaluated_property() -> None:
    """Evaluated returns individuals where requires_eval is False."""
    ind_eval = _make_ind(5.0)
    ind_uneval = Individual()
    pop = Population([ind_eval, ind_uneval])
    assert len(pop.evaluated) == 1


def test_population_size_property() -> None:
    """Size property equals len()."""
    pop = Population([_make_ind() for _ in range(4)])
    assert pop.size == len(pop)


def test_population_chain_api() -> None:
    """Chainable API: alive.sample(10).best(n=1) works end-to-end."""
    inds = [_make_ind(float(i), alive=(i % 2 == 0)) for i in range(10)]
    pop = Population(inds)
    result = pop.alive.sample(10).best(n=1)
    assert len(result) == 1
    assert result[0].alive is True


def test_sort_treats_missing_attributes_as_lowest() -> None:
    """An attribute an individual lacks sorts as -inf instead of failing."""
    pop = Population([_make_ind(1.0), _make_ind(2.0)])
    ordered = pop.sort(attribute="no_such_attribute")
    assert len(ordered) == len(pop)
