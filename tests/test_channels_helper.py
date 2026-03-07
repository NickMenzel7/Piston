from piston_ui.channels_helper import build_channels_spec


def test_build_channels_spec_counts():
    spec = build_channels_spec('2', '1', '1', freeform_spec='')
    # 2 single,1 dual,1 quad -> list with two 1s, one 2, one 4 -> uniq != 1 so list
    assert isinstance(spec, list)
    assert spec.count(1) == 2
    assert spec.count(2) == 1
    assert spec.count(4) == 1


def test_build_channels_spec_freeform_parse(monkeypatch):
    # provide a fake parser
    def fake_parse(spec, n_units=None):
        return [int(x) for x in spec.split(',')]
    spec = build_channels_spec('0', '0', '0', freeform_spec='1,2,4', parse_channels_fn=fake_parse)
    assert spec == [1,2,4]


def test_build_channels_spec_uniform():
    spec = build_channels_spec('1', '0', '0')
    assert spec == 1
