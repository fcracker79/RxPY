import unittest

from datetime import datetime, timedelta
import threading
from time import sleep
from rx.concurrency import EventLoopScheduler
from rx.internal import DisposedException


class TestEventLoopScheduler(unittest.TestCase):
    def test_event_loop_now(self):
        scheduler = EventLoopScheduler()
        res = scheduler.now - datetime.utcnow()

        assert res < timedelta(microseconds=1000)

    def test_event_loop_schedule_action(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        ran = False
        gate = threading.Semaphore(0)

        def action(scheduler, state):
            nonlocal ran
            ran = True
            gate.release()

        scheduler.schedule(action)
        gate.acquire()
        assert ran is True
        assert scheduler._has_thread() is False

    def test_event_loop_different_thread(self):
        thread_id = None
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)

        def action(scheduler, state):
            nonlocal thread_id
            thread_id = threading.current_thread().ident
            gate.release()

        scheduler.schedule(action)
        gate.acquire()
        assert thread_id != threading.current_thread().ident
        assert scheduler._has_thread() is False

    def test_event_loop_schedule_ordered_actions(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)
        result = []

        scheduler.schedule(lambda s, t: result.append(1))

        def action(scheduler, state):
            result.append(2)
            gate.release()

        scheduler.schedule(action)
        gate.acquire()
        assert result == [1, 2]
        assert scheduler._has_thread() is False

    def test_event_loop_schedule_ordered_actions_due(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)
        result = []

        def action(scheduler, state):
            result.append(3)
            gate.release()

        scheduler.schedule_relative(0.10, action)
        scheduler.schedule_relative(0.05, lambda s, t: result.append(2))
        scheduler.schedule(lambda s, t: result.append(1))

        gate.acquire()
        assert result == [1, 2, 3]
        assert scheduler._has_thread() is False

    def test_event_loop_schedule_ordered_actions_due_mixed(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)
        result = []

        def action(scheduler, state):
            result.append(1)
            scheduler.schedule(action2)
            scheduler.schedule_relative(0.10, action3)
            sleep(0.10)

        def action2(scheduler, state):
            result.append(2)

        def action3(scheduler, state):
            result.append(3)
            gate.release()

        scheduler.schedule(action)

        gate.acquire()
        assert result == [1, 2, 3]
        assert scheduler._has_thread() is False

    def test_event_loop_schedule_action_relative_due(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)
        starttime = datetime.utcnow()
        endtime = None

        def action(scheduler, state):
            nonlocal endtime
            endtime = datetime.utcnow()
            gate.release()

        scheduler.schedule_relative(timedelta(milliseconds=200), action)
        gate.acquire()
        diff = endtime - starttime
        assert diff > timedelta(milliseconds=180)
        assert scheduler._has_thread() is False

    def test_event_loop_schedule_action_absolute_due(self):
        scheduler = EventLoopScheduler(exit_if_empty=True)
        gate = threading.Semaphore(0)
        starttime = datetime.utcnow()
        endtime = None

        def action(scheduler, state):
            nonlocal endtime
            endtime = datetime.utcnow()
            gate.release()

        scheduler.schedule_absolute(scheduler.now, action)
        gate.acquire()
        diff = endtime - starttime
        assert diff < timedelta(milliseconds=180)
        assert scheduler._has_thread() is False

    def test_eventloop_schedule_action_periodic(self):
        scheduler = EventLoopScheduler(exit_if_empty=False)
        gate = threading.Semaphore(0)
        period = 0.05
        counter = 3

        def action(state):
            nonlocal counter
            if state:
                counter -= 1
                return state - 1
            if counter == 0:
                gate.release()

        disp = scheduler.schedule_periodic(period, action, counter)

        def dispose(scheduler, state):
            disp.dispose()
            gate.release()

        gate.acquire()
        assert counter == 0
        assert scheduler._has_thread() is True
        scheduler.schedule(dispose)
        gate.acquire()
        assert scheduler._has_thread() is True
        sleep(period)
        scheduler.dispose()
        sleep(period)
        assert scheduler._has_thread() is False

    def test_eventloop_schedule_dispose(self):
        scheduler = EventLoopScheduler(exit_if_empty=False)

        scheduler.dispose()

        ran = False

        def action(scheduler, state):
            nonlocal ran
            ran = True

        exc = None
        try:
            scheduler.schedule(action)
        except Exception as e:
            exc = e
        finally:
            assert isinstance(exc, DisposedException)
            assert ran is False
            assert scheduler._has_thread() is False

    def test_eventloop_schedule_absolute_dispose(self):
        scheduler = EventLoopScheduler(exit_if_empty=False)

        scheduler.dispose()

        ran = False

        def action(scheduler, state):
            nonlocal ran
            ran = True

        exc = None
        try:
            scheduler.schedule_absolute(scheduler.now, action)
        except Exception as e:
            exc = e
        finally:
            assert isinstance(exc, DisposedException)
            assert ran is False
            assert scheduler._has_thread() is False

    def test_eventloop_schedule_periodic_dispose(self):
        scheduler = EventLoopScheduler(exit_if_empty=False)

        scheduler.dispose()

        ran = False

        def action(scheduler, state):
            nonlocal ran
            ran = True

        exc = None
        try:
            scheduler.schedule_periodic(0.1, scheduler.now, action)
        except Exception as e:
            exc = e
        finally:
            assert isinstance(exc, DisposedException)
            assert ran is False
            assert scheduler._has_thread() is False
