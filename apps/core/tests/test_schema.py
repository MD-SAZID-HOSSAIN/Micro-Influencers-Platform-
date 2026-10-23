"""The API documentation and packaging must stay in step with the code."""
import re
from pathlib import Path

import pytest
import yaml
from django.core.management import call_command
from drf_spectacular.generators import SchemaGenerator

from apps.core.tests.test_security_matrix import PUBLIC_ROUTES

BASE_DIR = Path(__file__).resolve().parents[3]
EXPECTED_TAGS = {
    "Health",
    "Auth",
    "Profiles",
    "Social",
    "Discovery",
    "Campaigns",
    "Proposals",
    "Reviews",
    "Notifications",
    "Dashboards",
    "Admin",
}
HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


@pytest.fixture(scope="module")
def schema():
    return SchemaGenerator().get_schema(request=None, public=True)


def operations(schema):
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method in HTTP_METHODS:
                yield path, method, operation


# ---- Swagger / OpenAPI --------------------------------------------------------------------------


def test_schema_generation_has_no_warnings(tmp_path):
    call_command("spectacular", "--validate", "--fail-on-warn", "--file", str(tmp_path / "schema.yml"))


def test_every_operation_has_exactly_one_known_tag(schema):
    problems = [
        (method.upper(), path, operation.get("tags"))
        for path, method, operation in operations(schema)
        if len(operation.get("tags", [])) != 1 or operation["tags"][0] not in EXPECTED_TAGS
    ]

    assert problems == []


def test_every_tag_is_described_and_listed_in_order(schema):
    tags = schema["tags"]

    assert {t["name"] for t in tags} == EXPECTED_TAGS
    assert all(t.get("description") for t in tags)


def test_the_overview_explains_auth_errors_and_pagination(schema):
    description = schema["info"]["description"]

    for must_mention in ("Authorization: Bearer", "error", "page_size"):
        assert must_mention in description


def test_protected_operations_declare_bearer_auth_and_public_ones_do_not(schema):
    wrong = []
    for path, method, operation in operations(schema):
        protected = path not in PUBLIC_ROUTES
        declared = "bearerAuth" in {name for entry in operation.get("security", []) for name in entry}
        if protected != declared:
            wrong.append((method.upper(), path, "missing bearerAuth" if protected else "unexpected bearerAuth"))

    assert wrong == []
    assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"


def test_committed_openapi_file_matches_the_code(tmp_path):
    generated = tmp_path / "openapi.yml"
    call_command("spectacular", "--file", str(generated))
    committed = BASE_DIR / "docs" / "openapi.yml"

    assert committed.exists(), "run: python manage.py spectacular --file docs/openapi.yml"
    assert yaml.safe_load(committed.read_text(encoding="utf-8")) == yaml.safe_load(
        generated.read_text(encoding="utf-8")
    ), "docs/openapi.yml is stale. Regenerate: python manage.py spectacular --file docs/openapi.yml"


# ---- configuration is documented ------------------------------------------------------------------


def _settings_variables():
    names = set()
    for module in ("base.py", "prod.py"):
        source = (BASE_DIR / "config" / "settings" / module).read_text(encoding="utf-8")
        names |= set(re.findall(r'env(?:\.\w+)?\(\s*"([A-Z][A-Z0-9_]+)"', source))
    return names


def _env_example_variables():
    text = (BASE_DIR / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))


def test_env_example_lists_every_variable_the_settings_read():
    missing = _settings_variables() - _env_example_variables()

    assert missing == set(), f"Add these to .env.example: {sorted(missing)}"


def test_readme_documents_every_variable():
    readme = (BASE_DIR / "README.md").read_text(encoding="utf-8")
    missing = {name for name in _settings_variables() if f"`{name}`" not in readme}

    assert missing == set(), f"Document these in the README env table: {sorted(missing)}"


# ---- packaging --------------------------------------------------------------------------------------


def test_the_repository_ships_no_container_files():
    """The project runs on a locally installed PostgreSQL; there is deliberately no Docker setup."""
    for name in ("Dockerfile", "docker-compose.yml", ".dockerignore"):
        assert not (BASE_DIR / name).exists(), name


def test_production_server_gunicorn_is_a_dependency():
    assert "gunicorn" in (BASE_DIR / "requirements" / "base.txt").read_text(encoding="utf-8")


def test_deployment_guide_exists_and_covers_the_essentials():
    guide = (BASE_DIR / "docs" / "DEPLOYMENT.md").read_text(encoding="utf-8")

    for topic in ("NUM_PROXIES", "X-Forwarded-Proto", "beat", "migrate", "SPF", "refresh token"):
        assert topic in guide, topic
