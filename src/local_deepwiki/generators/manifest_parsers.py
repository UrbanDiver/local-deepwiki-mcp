"""Language-specific manifest parser functions.

Each parser reads a specific package manifest format and populates a
``ProjectManifest`` instance with extracted metadata.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from local_deepwiki.generators.manifest import ProjectManifest


def _parse_pyproject_toml(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse pyproject.toml (Python)."""
    import tomllib

    content = filepath.read_text()
    data = tomllib.loads(content)

    manifest.language = "Python"

    # Project metadata
    project = data.get("project", {})
    manifest.name = project.get("name")
    manifest.version = project.get("version")
    manifest.description = project.get("description")
    manifest.license = (
        project.get("license", {}).get("text")
        if isinstance(project.get("license"), dict)
        else project.get("license")
    )

    # Python version
    requires_python = project.get("requires-python")
    if requires_python:
        manifest.language_version = requires_python

    # Authors
    authors = project.get("authors", [])
    manifest.authors = [
        str(a.get("name") or a.get("email") or "")
        for a in authors
        if isinstance(a, dict)
    ]

    # Dependencies
    deps = project.get("dependencies", [])
    for dep in deps:
        name, version = _parse_python_dep(dep)
        manifest.dependencies[name] = version

    # Optional/dev dependencies
    optional = project.get("optional-dependencies", {})
    for group, deps in optional.items():
        for dep in deps:
            name, version = _parse_python_dep(dep)
            manifest.dev_dependencies[name] = version

    # Entry points / scripts
    scripts = project.get("scripts", {})
    manifest.entry_points.update(scripts)

    # Also check [tool.poetry] for Poetry projects
    poetry = data.get("tool", {}).get("poetry", {})
    if poetry:
        if not manifest.name:
            manifest.name = poetry.get("name")
        if not manifest.description:
            manifest.description = poetry.get("description")

        for name, spec in poetry.get("dependencies", {}).items():
            if name.lower() != "python":
                version = spec if isinstance(spec, str) else spec.get("version", "*")
                manifest.dependencies[name] = version

        for name, spec in poetry.get("dev-dependencies", {}).items():
            version = spec if isinstance(spec, str) else spec.get("version", "*")
            manifest.dev_dependencies[name] = version


def _parse_python_dep(dep: str) -> tuple[str, str]:
    """Parse a Python dependency string like 'requests>=2.0'."""
    # Match: package_name followed by optional version specifier
    match = re.match(r"^([a-zA-Z0-9_-]+)\s*(.*)$", dep.strip())
    if match:
        return match.group(1), match.group(2).strip() or "*"
    return dep, "*"


def _parse_setup_py(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse setup.py (Python legacy)."""
    content = filepath.read_text()
    manifest.language = "Python"

    # Extract name
    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
    if name_match and not manifest.name:
        manifest.name = name_match.group(1)

    # Extract version
    version_match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
    if version_match and not manifest.version:
        manifest.version = version_match.group(1)

    # Extract install_requires
    requires_match = re.search(r"install_requires\s*=\s*\[(.*?)\]", content, re.DOTALL)
    if requires_match:
        deps_str = requires_match.group(1)
        for dep_match in re.finditer(r'["\']([^"\']+)["\']', deps_str):
            name, version = _parse_python_dep(dep_match.group(1))
            if name not in manifest.dependencies:
                manifest.dependencies[name] = version


def _parse_requirements_txt(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse requirements.txt (Python)."""
    content = filepath.read_text()
    manifest.language = "Python"

    for line in content.splitlines():
        line = line.strip()
        # Skip comments and empty lines
        if not line or line.startswith("#") or line.startswith("-"):
            continue

        name, version = _parse_python_dep(line)
        if name and name not in manifest.dependencies:
            manifest.dependencies[name] = version


def _parse_package_json(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse package.json (Node.js)."""
    content = filepath.read_text()
    data = json.loads(content)

    # Determine if TypeScript or JavaScript
    deps = data.get("dependencies", {})
    dev_deps = data.get("devDependencies", {})
    all_deps = {**deps, **dev_deps}

    if "typescript" in all_deps:
        manifest.language = "TypeScript"
    else:
        manifest.language = "JavaScript"

    # Check for Node version in engines
    engines = data.get("engines", {})
    if "node" in engines:
        manifest.language_version = f"Node {engines['node']}"

    manifest.name = data.get("name")
    manifest.version = data.get("version")
    manifest.description = data.get("description")
    manifest.license = data.get("license")
    manifest.repository = (
        data.get("repository", {}).get("url")
        if isinstance(data.get("repository"), dict)
        else data.get("repository")
    )

    # Dependencies
    for name, version in deps.items():
        manifest.dependencies[name] = version

    for name, version in dev_deps.items():
        manifest.dev_dependencies[name] = version

    # Scripts
    manifest.scripts.update(data.get("scripts", {}))

    # Main entry point
    if data.get("main"):
        manifest.entry_points["main"] = data["main"]
    if data.get("bin"):
        bin_entry = data["bin"]
        if isinstance(bin_entry, str):
            manifest.entry_points[manifest.name or "bin"] = bin_entry
        elif isinstance(bin_entry, dict):
            manifest.entry_points.update(bin_entry)


def _parse_cargo_toml(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse Cargo.toml (Rust)."""
    import tomllib

    content = filepath.read_text()
    data = tomllib.loads(content)

    manifest.language = "Rust"

    package = data.get("package", {})
    manifest.name = package.get("name")
    manifest.version = package.get("version")
    manifest.description = package.get("description")
    manifest.license = package.get("license")

    # Rust edition as version
    if package.get("edition"):
        manifest.language_version = f"Edition {package['edition']}"

    # Dependencies
    for name, spec in data.get("dependencies", {}).items():
        if isinstance(spec, str):
            manifest.dependencies[name] = spec
        elif isinstance(spec, dict):
            manifest.dependencies[name] = spec.get("version", "*")

    for name, spec in data.get("dev-dependencies", {}).items():
        if isinstance(spec, str):
            manifest.dev_dependencies[name] = spec
        elif isinstance(spec, dict):
            manifest.dev_dependencies[name] = spec.get("version", "*")

    # Binary targets
    for bin_target in data.get("bin", []):
        if bin_target.get("name"):
            manifest.entry_points[bin_target["name"]] = bin_target.get("path", "")


def _parse_go_mod(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse go.mod (Go)."""
    content = filepath.read_text()
    manifest.language = "Go"

    # Module name
    module_match = re.search(r"^module\s+(\S+)", content, re.MULTILINE)
    if module_match:
        manifest.name = module_match.group(1).split("/")[-1]

    # Go version
    go_match = re.search(r"^go\s+(\S+)", content, re.MULTILINE)
    if go_match:
        manifest.language_version = go_match.group(1)

    # Dependencies (require block)
    require_block = re.search(r"require\s*\((.*?)\)", content, re.DOTALL)
    if require_block:
        for line in require_block.group(1).splitlines():
            line = line.strip()
            if line and not line.startswith("//"):
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0].split("/")[-1]  # Use last part of module path
                    version = parts[1]
                    manifest.dependencies[name] = version


def _pom_find(root: Any, path: str, ns: dict[str, str]) -> Any:
    """Find an XML element trying namespaced path first, then bare path."""
    result = root.find(path, ns)
    if result is None:
        result = root.find(path.replace("m:", ""))
    return result


def _pom_set_text_field(
    root: Any,
    xpath: str,
    ns: dict[str, str],
    manifest: "ProjectManifest",
    attr: str,
) -> None:
    """Set a manifest attribute from an XML element's text, if found."""
    elem = _pom_find(root, xpath, ns)
    if elem is not None and elem.text:
        setattr(manifest, attr, elem.text)


def _pom_parse_dependencies(
    root: Any, ns: dict[str, str], manifest: "ProjectManifest"
) -> None:
    """Parse Maven dependency elements into manifest dependencies."""
    deps = root.findall(".//m:dependency", ns) or root.findall(".//dependency")
    for dep in deps:
        artifact = dep.find("m:artifactId", ns) or dep.find("artifactId")
        version = dep.find("m:version", ns) or dep.find("version")
        scope = dep.find("m:scope", ns) or dep.find("scope")
        if artifact is not None and artifact.text:
            version_text = version.text if version is not None else "*"
            scope_text = scope.text if scope is not None else ""
            if scope_text == "test":
                manifest.dev_dependencies[artifact.text] = version_text or "*"
            else:
                manifest.dependencies[artifact.text] = version_text or "*"


def _parse_pom_xml(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse pom.xml (Java/Maven)."""
    import xml.etree.ElementTree as ET

    tree = ET.parse(filepath)
    root = tree.getroot()

    ns: dict[str, str] = {"m": "http://maven.apache.org/POM/4.0.0"}

    manifest.language = "Java"

    _pom_set_text_field(root, "m:artifactId", ns, manifest, "name")
    _pom_set_text_field(root, "m:version", ns, manifest, "version")
    _pom_set_text_field(root, "m:description", ns, manifest, "description")
    _pom_set_text_field(
        root, "m:properties/m:java.version", ns, manifest, "language_version"
    )

    _pom_parse_dependencies(root, ns, manifest)


def _parse_build_gradle(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse build.gradle (Java/Kotlin Gradle)."""
    content = filepath.read_text()

    # Detect Kotlin vs Java
    if "kotlin" in content.lower() or filepath.suffix == ".kts":
        manifest.language = "Kotlin"
    else:
        manifest.language = "Java"

    # Extract dependencies
    # Match: implementation 'group:artifact:version' or implementation "group:artifact:version"
    dep_pattern = re.compile(
        r'(?:implementation|api|compile)\s*[(\s]*["\']([^"\']+):([^"\']+):([^"\']+)["\']'
    )
    for match in dep_pattern.finditer(content):
        artifact, version = match.group(2), match.group(3)
        manifest.dependencies[artifact] = version

    # Test dependencies
    test_pattern = re.compile(
        r'(?:testImplementation|testCompile)\s*[(\s]*["\']([^"\']+):([^"\']+):([^"\']+)["\']'
    )
    for match in test_pattern.finditer(content):
        artifact, version = match.group(2), match.group(3)
        manifest.dev_dependencies[artifact] = version


def _parse_gemfile(filepath: Path, manifest: ProjectManifest) -> None:
    """Parse Gemfile (Ruby)."""
    content = filepath.read_text()
    manifest.language = "Ruby"

    # Extract gem dependencies
    # Match: gem 'name' or gem "name", "version"
    gem_pattern = re.compile(
        r'gem\s+["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']+)["\'])?'
    )
    for match in gem_pattern.finditer(content):
        name = match.group(1)
        version = match.group(2) or "*"
        manifest.dependencies[name] = version
