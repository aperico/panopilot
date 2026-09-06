from pathlib import Path

import panopilot.loading as loading_module


def _source():
    return Path(
        loading_module.__file__
    ).read_text(
        encoding="utf-8"
    )


def test_loading_fast_completion_is_explicitly_supported():
    source = _source()

    # Worker starts before modal exec; completion is polled after the modal
    # event loop starts. Therefore finishing "too quickly" cannot lose a quit
    # signal and leave the dialog stuck.
    assert source.index(
        "    worker.start()"
    ) < source.index(
        "    dialog.exec()"
    )
    assert "if worker.isFinished():" in source
    assert "dialog.accept()" in source


def test_loading_progress_crosses_thread_via_queue_not_widgets():
    source = _source()

    assert "SimpleQueue" in source
    assert "progress_queue.put" in source
    assert "status_label.setText" in source

    # PreparationThread.run itself must not touch the QLabel.
    run_start = source.index(
        "        def run(self):"
    )
    run_end = source.index(
        "    worker = PreparationThread()"
    )
    worker_run = source[
        run_start:run_end
    ]
    assert "status_label" not in worker_run
