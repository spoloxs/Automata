"""
Unit tests for Task and TaskDAG.
"""
import pytest
from web_agent.core.task import Task, TaskDAG, TaskStatus, TaskPriority


def test_task_creation():
    """Test basic task creation"""
    task = Task(
        description="Test task",
        dependencies=[],
        metadata={'test': True}
    )
    
    assert task.description == "Test task"
    assert task.status == TaskStatus.PENDING
    assert task.priority == TaskPriority.NORMAL
    assert task.id is not None
    assert len(task.id) == 12


def test_task_status_transitions():
    """Test task status transitions"""
    task = Task(description="Test")
    
    # Pending/Ready -> Running
    task.mark_running("worker_1")
    assert task.status == TaskStatus.RUNNING
    assert task.assigned_worker == "worker_1"
    
    # Running -> Completed
    task.mark_completed()
    assert task.status == TaskStatus.COMPLETED
    assert task.is_terminal()


def test_task_failure():
    """Test task failure"""
    task = Task(description="Test")
    task.mark_running("worker_1")
    task.mark_failed("Something went wrong")
    
    assert task.status == TaskStatus.FAILED
    assert task.error == "Something went wrong"
    assert task.is_terminal()


def test_dag_add_task():
    """Test adding tasks to DAG"""
    dag = TaskDAG()
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2")
    
    dag.add_task(task1)
    dag.add_task(task2)
    
    assert dag.get_task_count() == 2
    assert dag.get_task(task1.id) == task1
    assert dag.get_task(task2.id) == task2


def test_dag_dependencies():
    """Test DAG dependency management"""
    dag = TaskDAG()
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2", dependencies=[task1.id])
    
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_dependency(task2.id, task1.id)
    
    assert task1.id in task2.dependencies


def test_dag_ready_tasks():
    """Test getting ready tasks"""
    dag = TaskDAG()
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2", dependencies=[task1.id])
    
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_dependency(task2.id, task1.id)
    
    # Initially, only task1 should be ready
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == task1.id
    
    # After task1 completes, task2 should be ready
    task1.mark_running("worker_1")
    task1.mark_completed()
    ready = dag.get_ready_tasks()
    assert len(ready) == 1
    assert ready[0].id == task2.id


def test_dag_cycle_detection():
    """Test cycle detection in DAG"""
    dag = TaskDAG()
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2")
    
    dag.add_task(task1)
    dag.add_task(task2)
    
    # Create valid dependency: task2 -> task1
    dag.add_dependency(task2.id, task1.id)
    
    # Try to create cycle: task1 -> task2
    with pytest.raises(ValueError, match="cycle"):
        dag.add_dependency(task1.id, task2.id)


def test_dag_execution_order():
    """Test topological sort for execution order"""
    dag = TaskDAG()
    task1 = Task(description="Task 1")
    task2 = Task(description="Task 2", dependencies=[task1.id])
    task3 = Task(description="Task 3", dependencies=[task1.id])
    task4 = Task(description="Task 4", dependencies=[task2.id, task3.id])
    
    dag.add_task(task1)
    dag.add_task(task2)
    dag.add_task(task3)
    dag.add_task(task4)
    
    dag.add_dependency(task2.id, task1.id)
    dag.add_dependency(task3.id, task1.id)
    dag.add_dependency(task4.id, task2.id)
    dag.add_dependency(task4.id, task3.id)
    
    levels = dag.get_execution_order()
    
    # Level 0: task1
    assert len(levels[0]) == 1
    assert task1.id in levels[0]
    
    # Level 1: task2, task3 (parallel)
    assert len(levels[1]) == 2
    assert task2.id in levels[1]
    assert task3.id in levels[1]
    
    # Level 2: task4
    assert len(levels[2]) == 1
    assert task4.id in levels[2]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
