"""Exercise the one-command setup boundary without downloading runtimes."""
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmarks.__main__ import main


class CliTests(unittest.TestCase):
    def test_setup_precedes_measurement_and_preserves_runner_exit_status(self):
        events = []
        with patch('sys.argv', ['benchmarks', 'run', '--setup']), \
                patch('scripts.setup.ensure_installed', side_effect=lambda _: events.append('setup')), \
                patch('benchmarks.__main__.run', side_effect=lambda _: (events.append('run') or (Path('results/test'), 1))), \
                patch('benchmarks.report.generate', side_effect=lambda *a, **kw: events.append('report')), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 1)
        self.assertEqual(events, ['setup', 'run', 'report'])

    def test_explicit_toolchain_skips_install_and_preserves_arguments(self):
        with patch('sys.argv', ['benchmarks', 'run', '--setup', '--toolchain', 'custom tools.json',
                                '--label', 'with spaces', '--formats', 'svg']), \
                patch('scripts.setup.ensure_installed') as install, \
                patch('benchmarks.__main__.run', return_value=(Path('results/test'), 0)) as run, \
                patch('benchmarks.report.generate'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(), 0)
        install.assert_not_called()
        args = run.call_args.args[0]
        self.assertEqual(args.toolchain, Path('custom tools.json'))
        self.assertEqual(args.label, 'with spaces')
        self.assertEqual(args.formats, ['svg'])

    def test_help_and_invalid_options_do_not_install(self):
        for arguments, status in [(['--help'], 0), (['--repetitions', '0'], 2)]:
            with self.subTest(arguments=arguments), \
                    patch('sys.argv', ['benchmarks', 'run', '--setup', *arguments]), \
                    patch('scripts.setup.ensure_installed') as install, \
                    contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main()
                self.assertEqual(result.exception.code, status)
                install.assert_not_called()
