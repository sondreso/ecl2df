import os
import sys
import shutil

import pytest

import ecl2df.hook_implementations.jobs

try:
    from ert_shared.plugins.plugin_manager import ErtPluginManager
except ImportError:
    pytest.skip(
        "ERT is not installed, skipping hook implementations.", allow_module_level=True
    )


EXPECTED_JOBS = {
    "ECL2CSV": "ecl2df/config_jobs/ECL2CSV",
    "CSV2ECL": "ecl2df/config_jobs/CSV2ECL",
}


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
def test_hook_implementations():
    pm = ErtPluginManager(plugins=[ecl2df.hook_implementations.jobs])

    installable_jobs = pm.get_installable_jobs()
    for wf_name, wf_location in EXPECTED_JOBS.items():
        assert wf_name in installable_jobs
        assert installable_jobs[wf_name].endswith(wf_location)
        assert os.path.isfile(installable_jobs[wf_name])

    assert set(installable_jobs.keys()) == set(EXPECTED_JOBS.keys())

    expected_workflow_jobs = {}
    installable_workflow_jobs = pm.get_installable_workflow_jobs()
    for wf_name, wf_location in expected_workflow_jobs.items():
        assert wf_name in installable_workflow_jobs
        assert installable_workflow_jobs[wf_name].endswith(wf_location)

    assert set(installable_workflow_jobs.keys()) == set(expected_workflow_jobs.keys())


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
def test_job_config_syntax():
    """Check for syntax errors made in job configuration files"""
    src_path = os.path.join(os.path.dirname(__file__), "../")
    for _, job_config in EXPECTED_JOBS.items():
        # Check (loosely) that double-dashes are enclosed in quotes:
        with open(os.path.join(src_path, job_config)) as f_handle:
            for line in f_handle.readlines():
                if not line.strip().startswith("--") and "--" in line:
                    assert '"--' in line and " --" not in line


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
@pytest.mark.integration
def test_executables():
    """Test executables listed in job configurations exist in $PATH"""
    src_path = os.path.join(os.path.dirname(__file__), "../")
    for _, job_config in EXPECTED_JOBS.items():
        with open(os.path.join(src_path, job_config)) as f_handle:
            executable = f_handle.readlines()[0].split()[1]
            assert shutil.which(executable)


@pytest.mark.skipif(sys.version_info < (3, 6), reason="requires python3.6 or higher")
def test_hook_implementations_job_docs():
    pm = ErtPluginManager(plugins=[ecl2df.hook_implementations.jobs])

    installable_jobs = pm.get_installable_jobs()

    docs = pm.get_documentation_for_jobs()

    assert set(docs.keys()) == set(installable_jobs.keys())

    for job_name in installable_jobs.keys():
        print(job_name)
        assert docs[job_name]["description"] != ""
        assert docs[job_name]["category"] != "other"