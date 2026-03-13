"""Tests for Task Scheduler sync — mock subprocess."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pywinhello.monitor.scheduler_sync import (
    ScheduleConfig,
    _build_task_xml,
    create_wake_task,
    delete_all_tasks,
    delete_wake_task,
    sync_schedule,
    task_exists,
)


class TestScheduleConfig:
    def test_from_pico_config(self):
        config = {
            "schedule": {
                "time": "07:45",
                "days": [1, 2, 3, 4, 5],
                "enabled": True,
            }
        }
        sched = ScheduleConfig.from_pico_config(config)
        assert sched is not None
        assert sched.time == "07:45"
        assert sched.days == [1, 2, 3, 4, 5]
        assert sched.enabled is True

    def test_from_pico_config_string_days(self):
        config = {
            "schedule": {
                "time": "08:00",
                "days": ["mon", "wed", "fri"],
            }
        }
        sched = ScheduleConfig.from_pico_config(config)
        assert sched is not None
        assert sched.days == [1, 3, 5]

    def test_from_pico_config_no_schedule(self):
        assert ScheduleConfig.from_pico_config({}) is None

    def test_from_pico_config_empty_schedule(self):
        assert ScheduleConfig.from_pico_config({"schedule": {}}) is None

    def test_from_pico_config_no_time(self):
        config = {"schedule": {"days": [1, 2, 3]}}
        assert ScheduleConfig.from_pico_config(config) is None

    def test_from_pico_config_no_days(self):
        config = {"schedule": {"time": "07:00"}}
        assert ScheduleConfig.from_pico_config(config) is None

    def test_from_pico_config_disabled(self):
        config = {
            "schedule": {
                "time": "07:45",
                "days": [1, 2, 3, 4, 5],
                "enabled": False,
            }
        }
        sched = ScheduleConfig.from_pico_config(config)
        assert sched is not None
        assert sched.enabled is False


class TestBuildTaskXml:
    def test_xml_contains_wake(self):
        xml = _build_task_xml("07:45", "MON,TUE,WED", "test.exe")
        assert "<WakeToRun>true</WakeToRun>" in xml

    def test_xml_contains_days(self):
        xml = _build_task_xml("07:45", "MON,FRI", "test.exe")
        assert "<Monday />" in xml
        assert "<Friday />" in xml
        assert "<Tuesday />" not in xml

    def test_xml_contains_time(self):
        xml = _build_task_xml("08:30", "MON", "test.exe")
        assert "T08:30:00" in xml

    def test_xml_contains_exe(self):
        xml = _build_task_xml("07:00", "MON", "C:\\path\\to\\pywinhello.exe")
        assert "C:\\path\\to\\pywinhello.exe" in xml

    def test_xml_contains_wake_argument(self):
        xml = _build_task_xml("07:00", "MON", "test.exe")
        assert "<Arguments>wake</Arguments>" in xml


class TestTaskExists:
    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_task_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        assert task_exists("pywinhello-wake") is True
        mock_run.assert_called_with("/query", "/tn", "pywinhello-wake", check=False)

    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_task_not_exists(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        assert task_exists("pywinhello-wake") is False


class TestDeleteWakeTask:
    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_delete_existing(self, mock_run):
        # task_exists returns success, delete returns success
        mock_run.side_effect = [
            MagicMock(returncode=0),  # /query (exists check)
            MagicMock(returncode=0),  # /delete
        ]
        assert delete_wake_task() is True

    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_delete_nonexistent(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)  # not found
        assert delete_wake_task() is True  # Idempotent


class TestDeleteAllTasks:
    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_delete_multiple(self, mock_run):
        # Query returns CSV with matching tasks
        query_result = MagicMock(
            returncode=0,
            stdout='"\\pywinhello-wake","Ready"\n"\\pywinhello-other","Ready"\n"\\unrelated","Ready"\n',
        )
        delete_result = MagicMock(returncode=0)
        mock_run.side_effect = [query_result, delete_result, delete_result]

        deleted = delete_all_tasks()
        assert deleted == 2

    @patch("pywinhello.monitor.scheduler_sync._run_schtasks")
    def test_delete_none_matching(self, mock_run):
        query_result = MagicMock(
            returncode=0,
            stdout='"\\unrelated-task","Ready"\n',
        )
        mock_run.return_value = query_result

        assert delete_all_tasks() == 0


class TestCreateWakeTask:
    @patch("pywinhello.monitor.scheduler_sync._create_task_from_xml")
    @patch("pywinhello.monitor.scheduler_sync.delete_wake_task", return_value=True)
    def test_create_task(self, mock_delete, mock_create):
        schedule = ScheduleConfig(time="07:45", days=[1, 2, 3, 4, 5])
        result = create_wake_task(schedule)

        assert result is True
        mock_delete.assert_called_once()
        mock_create.assert_called_once()

    @patch("pywinhello.monitor.scheduler_sync.delete_wake_task", return_value=True)
    def test_create_disabled_deletes(self, mock_delete):
        schedule = ScheduleConfig(time="07:45", days=[1, 2, 3, 4, 5], enabled=False)
        result = create_wake_task(schedule)

        assert result is True
        mock_delete.assert_called()

    @patch("pywinhello.monitor.scheduler_sync._create_task_from_xml")
    @patch("pywinhello.monitor.scheduler_sync.delete_wake_task", return_value=True)
    def test_create_invalid_days(self, mock_delete, mock_create):
        schedule = ScheduleConfig(time="07:45", days=[99])
        result = create_wake_task(schedule)

        assert result is False
        mock_create.assert_not_called()


class TestSyncSchedule:
    @patch("pywinhello.monitor.scheduler_sync.create_wake_task", return_value=True)
    def test_sync_with_schedule(self, mock_create):
        config = {
            "schedule": {
                "time": "07:45",
                "days": [1, 2, 3, 4, 5],
                "enabled": True,
            }
        }
        assert sync_schedule(config) is True
        mock_create.assert_called_once()

    @patch("pywinhello.monitor.scheduler_sync.delete_all_tasks", return_value=1)
    def test_sync_no_schedule(self, mock_delete):
        assert sync_schedule({}) is True
        mock_delete.assert_called_once()

    @patch("pywinhello.monitor.scheduler_sync.delete_all_tasks", return_value=1)
    def test_sync_disabled_schedule(self, mock_delete):
        config = {
            "schedule": {
                "time": "07:45",
                "days": [1, 2, 3, 4, 5],
                "enabled": False,
            }
        }
        assert sync_schedule(config) is True
        mock_delete.assert_called_once()
