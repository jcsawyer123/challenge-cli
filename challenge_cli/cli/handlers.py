"""
Command handlers for Challenge CLI - business logic separated from CLI interface.
"""

from typing import Optional

from challenge_cli.core.logging import (
    log_context,
    log_error,
    log_info,
    log_warning,
    logged_operation,
)
from challenge_cli.plugins.docker_utils import shutdown_all_containers
from challenge_cli.tester import ChallengeTester

from .options import ResolvedOptions


class CommandHandlers:
    """Handles the business logic for CLI commands."""

    @staticmethod
    def create_tester(options: ResolvedOptions, challenge_path: str) -> ChallengeTester:
        """Factory method to create ChallengeTester with common parameters."""
        return ChallengeTester(
            platform=options.platform,
            challenge_path=challenge_path,
            language=options.language,
            problems_dir=options.problems_dir,
            use_history=options.use_history,
            max_snapshots=options.max_snapshots,
        )

    @staticmethod
    @logged_operation("init_command")
    def handle_init(
        options: ResolvedOptions,
        challenge_path: str,
        language: str,
        function_name: str,
    ):
        """Handle the init command."""
        with log_context(
            platform=options.platform, challenge=challenge_path, language=language
        ):
            log_info(
                f"Initializing challenge '{challenge_path}' for {language} (function: {function_name})"
            )
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.init_problem(language=language, function_name=function_name)
            log_info(
                f"Successfully initialized challenge '{challenge_path}' for {language}."
            )

    @staticmethod
    @logged_operation("test_command")
    def handle_test(
        options: ResolvedOptions,
        challenge_path: str,
        detailed: bool,
        cases: Optional[str],
        comment: Optional[str],
        tag: Optional[str],
    ):
        """Handle the test command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            log_info(
                f"Running tests for challenge '{challenge_path}' (detailed={detailed}, cases={cases}, comment={comment}, tag={tag})"
            )
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.run_tests(
                language=options.language,
                detailed=detailed,
                cases_arg=cases,
                snapshot_comment=comment,
                snapshot_tag=tag,
            )

    @staticmethod
    @logged_operation("profile_command")
    def handle_profile(
        options: ResolvedOptions,
        challenge_path: str,
        iterations: int,
        detailed: bool,
        cases: Optional[str],
        comment: Optional[str],
        tag: Optional[str],
    ):
        """Handle the profile command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            log_info(
                f"Profiling challenge '{challenge_path}' (iterations={iterations}, detailed={detailed}, cases={cases}, comment={comment}, tag={tag})"
            )
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.profile(
                language=options.language,
                iterations=iterations,
                detailed=detailed,
                cases_arg=cases,
                snapshot_comment=comment,
                snapshot_tag=tag,
            )

    @staticmethod
    @logged_operation("analyze_command")
    def handle_analyze(options: ResolvedOptions, challenge_path: str, language: str):
        """Handle the analyze command."""
        final_language = options.language or language
        with log_context(
            platform=options.platform, challenge=challenge_path, language=final_language
        ):
            if final_language != "python":
                log_error("Analysis currently only supports Python ('-l python').")
                raise ValueError("Analysis only supports Python")
            log_info(
                f"Analyzing complexity for challenge '{challenge_path}' in {final_language}"
            )
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.analyze_complexity(language=final_language)

    @staticmethod
    @logged_operation("clean_command")
    def handle_clean(options: ResolvedOptions):
        """Handle the clean command."""
        with log_context(platform=options.platform):
            log_info("Shutting down all running challenge containers")
            shutdown_all_containers()
            log_info(
                f"Shutdown all running challenge containers for platform '{options.platform}'."
            )


class HistoryCommandHandlers:
    """Handles the business logic for history-related commands."""

    @staticmethod
    def ensure_history_enabled(options: ResolvedOptions):
        """Ensure history is enabled or raise an exception."""
        if not options.use_history:
            log_warning("History command attempted but history is disabled")
            raise ValueError("History is disabled. Cannot perform history operations.")

    @staticmethod
    @logged_operation("history_list_command")
    def handle_list(options: ResolvedOptions, challenge_path: str, limit: int):
        """Handle the history list command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            HistoryCommandHandlers.ensure_history_enabled(options)
            log_info(f"Listing history (limit={limit})")
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.list_history(language=options.language, limit=limit)

    @staticmethod
    @logged_operation("history_show_command")
    def handle_show(options: ResolvedOptions, challenge_path: str, snapshot_id: str):
        """Handle the history show command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            HistoryCommandHandlers.ensure_history_enabled(options)
            log_info(f"Showing snapshot {snapshot_id}")
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.show_snapshot(snapshot_id)

    @staticmethod
    @logged_operation("history_compare_command")
    def handle_compare(
        options: ResolvedOptions, challenge_path: str, snapshot1: str, snapshot2: str
    ):
        """Handle the history compare command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            HistoryCommandHandlers.ensure_history_enabled(options)
            log_info(f"Comparing snapshots {snapshot1} and {snapshot2}")
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.compare_snapshots(snapshot1, snapshot2)

    @staticmethod
    @logged_operation("history_restore_command")
    def handle_restore(
        options: ResolvedOptions, challenge_path: str, snapshot_id: str, backup: bool
    ):
        """Handle the history restore command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            HistoryCommandHandlers.ensure_history_enabled(options)
            log_info(f"Restoring snapshot {snapshot_id} (backup={backup})")
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.restore_snapshot(snapshot_id, backup=backup)

    @staticmethod
    @logged_operation("history_visualize_command")
    def handle_visualize(
        options: ResolvedOptions,
        challenge_path: str,
        output_path: Optional[str],
        cases: Optional[str],
    ):
        """Handle the history visualize command."""
        with log_context(
            platform=options.platform,
            challenge=challenge_path,
            language=options.language,
        ):
            HistoryCommandHandlers.ensure_history_enabled(options)
            log_info(f"Generating visualization (output={output_path}, cases={cases})")
            tester = CommandHandlers.create_tester(options, challenge_path)
            tester.visualize_history(
                language=options.language, output_path=output_path, cases_arg=cases
            )
