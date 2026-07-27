from app.infrastructure.db.base import Base


def test_metadata_uses_stable_constraint_names() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"
    assert Base.metadata.naming_convention["fk"].startswith("fk_")
