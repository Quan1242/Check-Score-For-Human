import json
from pathlib import Path

import pytest

NOTEBOOK = Path(__file__).resolve().parents[2] / 'colab/instance_segmentation.ipynb'


def helper():
    notebook = json.loads(NOTEBOOK.read_text(encoding='utf-8'))
    namespace = {'__name__': 'colab_polygon_validation'}
    for cell in notebook['cells']:
        text = ''.join(cell['source'])
        if cell['cell_type'] == 'code' and not text.startswith('%'):
            compile(text, str(NOTEBOOK), 'exec')
        if 'M49_POLYGON_VALIDATION' in text:
            exec(compile(text, str(NOTEBOOK), 'exec'), namespace)
    return namespace['validate_polygon']


def test_notebook_polygon_matches_backend_contract():
    from app.schemas import Polygon
    validate = helper()
    points = [[1,1],[10,1],[10,10],[1,10],[1,1]]
    result = validate(points, 100, 80)
    assert len(result) == 4
    assert Polygon(kind='polygon', points=result).points == [(1,1),(10,1),(10,10),(1,10)]


@pytest.mark.parametrize('points', [
    [[1,1],[10,10],[1,10],[10,1]],
    [[1,1],[101,1],[10,10]],
    [[1,1],[float('nan'),2],[10,10]],
    [[1,1],[2,2],[3,3]],
])
def test_notebook_rejects_invalid_model_polygon(points):
    with pytest.raises(ValueError):
        helper()(points, 100, 80)
