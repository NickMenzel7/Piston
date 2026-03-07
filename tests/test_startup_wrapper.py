import pathlib


def test_startup_wrapper_present():
    """Fail if the `if __name__ == '__main__':` startup wrapper is missing from Piston.py.
    This ensures CI or local pytest will catch accidental removals.
    """
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    piston_path = repo_root / 'Piston.py'
    assert piston_path.exists(), f"Piston.py not found at {piston_path}"
    content = piston_path.read_text(encoding='utf-8')
    assert "if __name__ == '__main__':" in content, (
        "Startup wrapper `if __name__ == '__main__':` is missing from Piston.py.\n"
        "Add the robust startup block to the end of the file to ensure the GUI reports startup errors."
    )
