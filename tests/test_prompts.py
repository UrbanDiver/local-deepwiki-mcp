"""Tests for the custom prompt template system."""

from local_deepwiki.prompts import (
    PromptLoader,
    PromptManager,
    PromptTemplate,
    get_prompt_manager,
)


class TestPromptTemplate:
    """Tests for PromptTemplate class."""

    def test_basic_creation(self):
        """Test creating a basic template."""
        template = PromptTemplate("Hello, world!")
        assert template.template == "Hello, world!"
        assert template.source == "default"

    def test_creation_with_source(self):
        """Test creating template with custom source."""
        template = PromptTemplate("Hello", source="/path/to/file.md")
        assert template.source == "/path/to/file.md"

    def test_render_without_variables(self):
        """Test rendering template without variables."""
        template = PromptTemplate("Static text")
        result = template.render()
        assert result == "Static text"

    def test_render_with_single_variable(self):
        """Test rendering template with one variable."""
        template = PromptTemplate("Hello, {name}!")
        result = template.render(name="World")
        assert result == "Hello, World!"

    def test_render_with_multiple_variables(self):
        """Test rendering template with multiple variables."""
        template = PromptTemplate("Document the {language} code in {file_path}")
        result = template.render(language="Python", file_path="src/main.py")
        assert result == "Document the Python code in src/main.py"

    def test_render_with_unused_variable(self):
        """Test that unused variables are ignored."""
        template = PromptTemplate("Hello, {name}!")
        result = template.render(name="World", unused="value")
        assert result == "Hello, World!"

    def test_render_with_missing_variable(self):
        """Test that missing variables remain as placeholders."""
        template = PromptTemplate("Hello, {name}!")
        result = template.render()
        assert result == "Hello, {name}!"

    def test_get_variables(self):
        """Test extracting variable names from template."""
        template = PromptTemplate("Hello {name}, welcome to {place}!")
        variables = template.get_variables()
        assert set(variables) == {"name", "place"}

    def test_get_variables_empty(self):
        """Test extracting variables from template without any."""
        template = PromptTemplate("No variables here")
        variables = template.get_variables()
        assert variables == []

    def test_str_returns_template(self):
        """Test that str() returns the template string."""
        template = PromptTemplate("Hello, world!")
        assert str(template) == "Hello, world!"


class TestPromptLoader:
    """Tests for PromptLoader class."""

    def test_empty_search_paths(self):
        """Test loader with no valid search paths."""
        loader = PromptLoader()
        paths = loader._get_search_paths()
        # Should only have home config if it exists
        assert isinstance(paths, list)

    def test_custom_dir_in_search_paths(self, tmp_path):
        """Test that custom_dir is included in search paths."""
        custom_dir = tmp_path / "prompts"
        custom_dir.mkdir()

        loader = PromptLoader(custom_dir=custom_dir)
        paths = loader._get_search_paths()

        assert custom_dir in paths
        assert paths[0] == custom_dir  # Should be first (highest priority)

    def test_repo_prompts_in_search_paths(self, tmp_path):
        """Test that repo's .deepwiki/prompts is included."""
        repo_prompts = tmp_path / ".deepwiki" / "prompts"
        repo_prompts.mkdir(parents=True)

        loader = PromptLoader(repo_path=tmp_path)
        paths = loader._get_search_paths()

        assert repo_prompts in paths

    def test_load_prompt_from_file(self, tmp_path):
        """Test loading a prompt from file."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        prompt_file = prompts_dir / "wiki_system.md"
        prompt_file.write_text("Custom wiki system prompt")

        loader = PromptLoader(custom_dir=prompts_dir)
        template = loader.load_prompt("wiki_system", "Default prompt")

        assert template.template == "Custom wiki system prompt"
        assert str(prompt_file) in template.source

    def test_load_prompt_txt_extension(self, tmp_path):
        """Test loading prompt from .txt file."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        prompt_file = prompts_dir / "wiki_system.txt"
        prompt_file.write_text("Text file prompt")

        loader = PromptLoader(custom_dir=prompts_dir)
        template = loader.load_prompt("wiki_system", "Default")

        assert template.template == "Text file prompt"

    def test_load_prompt_provider_specific(self, tmp_path):
        """Test loading provider-specific prompt."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        # Generic prompt
        (prompts_dir / "wiki_system.md").write_text("Generic prompt")
        # Provider-specific prompt
        (prompts_dir / "wiki_system.anthropic.md").write_text("Anthropic prompt")

        loader = PromptLoader(custom_dir=prompts_dir)

        # Should get provider-specific
        template = loader.load_prompt("wiki_system", "Default", provider="anthropic")
        assert template.template == "Anthropic prompt"

        # Should get generic for other providers
        loader.clear_cache()
        template = loader.load_prompt("wiki_system", "Default", provider="ollama")
        assert template.template == "Generic prompt"

    def test_load_prompt_falls_back_to_default(self, tmp_path):
        """Test fallback to default when no file found."""
        loader = PromptLoader(custom_dir=tmp_path)
        template = loader.load_prompt("nonexistent", "Default prompt text")

        assert template.template == "Default prompt text"
        assert template.source == "built-in default"

    def test_prompt_caching(self, tmp_path):
        """Test that prompts are cached."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        prompt_file = prompts_dir / "wiki_system.md"
        prompt_file.write_text("Original content")

        loader = PromptLoader(custom_dir=prompts_dir)

        # First load
        template1 = loader.load_prompt("wiki_system", "Default")
        assert template1.template == "Original content"

        # Modify file
        prompt_file.write_text("Modified content")

        # Should still return cached version
        template2 = loader.load_prompt("wiki_system", "Default")
        assert template2.template == "Original content"

        # Clear cache and reload
        loader.clear_cache()
        template3 = loader.load_prompt("wiki_system", "Default")
        assert template3.template == "Modified content"

    def test_priority_custom_over_repo(self, tmp_path):
        """Test that custom_dir has priority over repo prompts."""
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        repo_prompts = repo_dir / ".deepwiki" / "prompts"
        repo_prompts.mkdir(parents=True)

        (custom_dir / "wiki_system.md").write_text("Custom prompt")
        (repo_prompts / "wiki_system.md").write_text("Repo prompt")

        loader = PromptLoader(custom_dir=custom_dir, repo_path=repo_dir)
        template = loader.load_prompt("wiki_system", "Default")

        assert template.template == "Custom prompt"


class TestPromptManager:
    """Tests for PromptManager class."""

    def test_get_wiki_system_prompt_default(self):
        """Test getting default wiki system prompt."""
        manager = PromptManager()
        prompt = manager.get_wiki_system_prompt(provider="anthropic")

        # Should contain some expected content from default prompt
        assert "documentation" in prompt.lower()

    def test_get_wiki_system_prompt_with_variables(self, tmp_path):
        """Test getting wiki prompt with variables."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "wiki_system.md").write_text(
            "Document the {language} code for {project_name}"
        )

        manager = PromptManager(custom_dir=prompts_dir)
        prompt = manager.get_wiki_system_prompt(
            provider="anthropic",
            language="Python",
            project_name="MyProject",
        )

        assert prompt == "Document the Python code for MyProject"

    def test_get_research_decomposition_prompt(self):
        """Test getting research decomposition prompt."""
        manager = PromptManager()
        prompt = manager.get_research_decomposition_prompt(provider="anthropic")

        # Should be non-empty
        assert len(prompt) > 0

    def test_get_research_gap_analysis_prompt(self):
        """Test getting research gap analysis prompt."""
        manager = PromptManager()
        prompt = manager.get_research_gap_analysis_prompt(provider="anthropic")

        assert len(prompt) > 0

    def test_get_research_synthesis_prompt(self):
        """Test getting research synthesis prompt."""
        manager = PromptManager()
        prompt = manager.get_research_synthesis_prompt(provider="anthropic")

        assert len(prompt) > 0

    def test_custom_prompts_override_defaults(self, tmp_path):
        """Test that custom prompts override defaults."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "wiki_system.md").write_text("My custom wiki prompt")
        (prompts_dir / "research_synthesis.md").write_text("My custom synthesis")

        manager = PromptManager(custom_dir=prompts_dir)

        wiki_prompt = manager.get_wiki_system_prompt(provider="anthropic")
        assert wiki_prompt == "My custom wiki prompt"

        synthesis_prompt = manager.get_research_synthesis_prompt(provider="anthropic")
        assert synthesis_prompt == "My custom synthesis"

    def test_provider_specific_custom_prompts(self, tmp_path):
        """Test provider-specific custom prompts."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()

        (prompts_dir / "wiki_system.anthropic.md").write_text("Claude-specific prompt")
        (prompts_dir / "wiki_system.ollama.md").write_text("Ollama-specific prompt")

        manager = PromptManager(custom_dir=prompts_dir)

        claude_prompt = manager.get_wiki_system_prompt(provider="anthropic")
        assert claude_prompt == "Claude-specific prompt"

        manager.loader.clear_cache()
        ollama_prompt = manager.get_wiki_system_prompt(provider="ollama")
        assert ollama_prompt == "Ollama-specific prompt"


class TestGetPromptManager:
    """Tests for get_prompt_manager factory function."""

    def test_creates_manager(self):
        """Test that factory creates a manager."""
        manager = get_prompt_manager()
        assert isinstance(manager, PromptManager)

    def test_passes_custom_dir(self, tmp_path):
        """Test that custom_dir is passed to manager."""
        custom_prompts = tmp_path / "prompts"
        custom_prompts.mkdir()

        manager = get_prompt_manager(custom_dir=custom_prompts)
        assert manager.loader.custom_dir == custom_prompts

    def test_passes_repo_path(self, tmp_path):
        """Test that repo_path is passed to manager."""
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()
        manager = get_prompt_manager(repo_path=repo_dir)
        assert manager.loader.repo_path == repo_dir
