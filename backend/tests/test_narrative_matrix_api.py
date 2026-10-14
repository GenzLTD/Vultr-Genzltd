"""叙事引擎 interaction matrix 接口 —— 回归：set 不可 JSON 序列化导致 500。

背景（2026-10-14 生产实测，api.genz.ltd / stack-v0.1.5）：

    GET /v1/narrative/engine/matrix   ->  HTTP 500（匿名 / 带 Bearer / 带查询参数均恒定）

    真机 traceback 落在：
        narrative_routes.py:363  return jsonify(matrix=matrix, domains=VALID_DOMAINS)
        flask/json/provider.py    raise TypeError(
            f"Object of type {type(o).__name__} is not JSON serializable")
        TypeError: Object of type set is not JSON serializable

    Flask 3 的默认 JSON provider 走 json.dumps，不接受 set；VALID_DOMAINS 是 set。

本测试钉住修复后的行为与响应形状，防止再次退化为 500：
  - 200，且 domains 是**列表**（非 set 语义）
  - domains 有序（sorted），保证响应可比对
  - matrix 非空；每个单元格含 level / description
  - matrix 的源域必须都出现在 domains 里（两处口径不漂移）

注：该路由是公开参考接口（docstring: public, for reference），
    因此不带鉴权即为预期行为，本测试不覆盖鉴权。
"""


def _get_matrix(client):
    resp = client.get("/v1/narrative/engine/matrix")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()


def test_matrix_is_not_500_and_domains_is_list(client):
    """回归：曾因 set 序列化失败恒 500 —— 现在必须 200 且 domains 为 list。"""
    data = _get_matrix(client)
    assert isinstance(data["domains"], list), f"domains 应为 list，实得 {type(data['domains'])}"
    assert data["domains"], "domains 不应为空"
    assert data["domains"] == sorted(data["domains"]), "domains 应有序（sorted），保证响应可比对"


def test_matrix_cells_have_level_and_description(client):
    data = _get_matrix(client)
    matrix = data["matrix"]
    assert isinstance(matrix, dict) and matrix, "matrix 不应为空"

    cells = 0
    for src, row in matrix.items():
        assert isinstance(row, dict), f"{src} 应为 dict"
        for tgt, cell in row.items():
            assert set(cell) == {"level", "description"}, f"{src}->{tgt} 字段应为 level/description"
            assert isinstance(cell["level"], str) and cell["level"], "level 应为非空字符串"
            assert isinstance(cell["description"], str), "description 应为字符串"
            cells += 1
    assert cells >= 1, "矩阵至少应有一个单元格"


def test_matrix_source_domains_are_declared(client):
    """矩阵里出现的源域，必须都在 domains 声明表内 —— 两处口径不漂移。"""
    data = _get_matrix(client)
    declared = set(data["domains"])
    used = set(data["matrix"])
    assert used, "matrix 源域不应为空"
    assert used <= declared, f"matrix 源域未在 domains 中声明: {sorted(used - declared)}"
