from src.services.pipeline import _combine_results, _extract_ingredients, _format_prices, _format_recipes


def test_extract_ingredients_basic():
    result = _extract_ingredients("pork and curry powder")
    assert "pork" in result
    assert "curry" in result
    assert "powder" in result
    assert "and" not in result


def test_extract_ingredients_filters_stop_words():
    result = _extract_ingredients("I would like to cook something with chicken")
    assert "chicken" in result
    assert "would" not in result
    assert "like" not in result


def test_combine_deduplicates():
    fts = [
        {"id": 1, "name": "A", "score": 0.8, "source": "fts"},
        {"id": 2, "name": "B", "score": 0.6, "source": "fts"},
    ]
    sem = [
        {"id": 2, "name": "B", "score": 0.5, "source": "semantic"},
        {"id": 3, "name": "C", "score": 0.4, "source": "semantic"},
    ]
    result = _combine_results(fts, sem)
    ids = [r["id"] for r in result]
    assert 1 in ids
    assert 2 in ids
    assert 3 in ids
    assert len(ids) == len(set(ids))


def test_combine_empty():
    assert _combine_results([], []) == []


def test_combine_respects_top_n(monkeypatch):
    monkeypatch.setattr("src.services.pipeline.settings.search_top_n", 2)
    monkeypatch.setattr("src.services.pipeline.settings.relevance_threshold", 0.0)
    items = [{"id": i, "name": f"R{i}", "score": 1.0 - i * 0.1, "source": "fts"} for i in range(5)]
    result = _combine_results(items, [])
    assert len(result) == 2


def test_combine_sorts_by_score():
    fts = [{"id": 1, "name": "Low", "score": 0.3, "source": "fts"}]
    sem = [{"id": 2, "name": "High", "score": 0.9, "source": "semantic"}]
    result = _combine_results(fts, sem)
    assert result[0]["id"] == 2
    assert result[1]["id"] == 1


def test_combine_takes_max_score():
    fts = [{"id": 1, "name": "A", "score": 0.3, "source": "fts"}]
    sem = [{"id": 1, "name": "A", "score": 0.8, "source": "semantic"}]
    result = _combine_results(fts, sem)
    assert len(result) == 1
    assert result[0]["score"] == 0.8
    assert result[0]["source"] == "both"


def test_combine_or_filter(monkeypatch):
    monkeypatch.setattr("src.services.pipeline.settings.relevance_threshold", 0.5)
    fts = [{"id": 1, "name": "FTS only", "score": 0.8, "source": "fts"}]
    sem = [{"id": 2, "name": "Sem only", "score": 0.6, "source": "semantic"}]
    result = _combine_results(fts, sem)
    assert len(result) == 2


def test_combine_filters_below_both_thresholds(monkeypatch):
    monkeypatch.setattr("src.services.pipeline.settings.relevance_threshold", 0.5)
    fts = [
        {"id": 1, "name": "Good", "score": 0.8, "source": "fts"},
        {"id": 2, "name": "Bad", "score": 0.2, "source": "fts"},
    ]
    result = _combine_results(fts, [])
    assert len(result) == 1
    assert result[0]["id"] == 1


def test_format_recipes_basic():
    recipes = [
        {
            "name": "Pasta",
            "ingredients": ["pasta", "sauce"],
            "steps": ["boil", "mix"],
            "minutes": 15,
        }
    ]
    text = _format_recipes(recipes)
    assert "Pasta" in text
    assert "pasta, sauce" in text
    assert "15 мин" in text


def test_format_recipes_empty():
    assert _format_recipes([]) == ""


def test_format_recipes_truncates_steps():
    recipes = [
        {
            "name": "Complex",
            "ingredients": ["a"],
            "steps": ["s1", "s2", "s3", "s4", "s5", "s6", "s7"],
            "minutes": 60,
        }
    ]
    text = _format_recipes(recipes)
    assert "..." in text


def test_format_prices():
    prices = {"молоко": 80.0, "хлеб": 50.0, "икра": None}
    text = _format_prices(prices)
    assert "молоко: 80 руб." in text
    assert "хлеб: 50 руб." in text
    assert "икра" not in text


def test_format_prices_empty():
    assert _format_prices({}) == ""
