"""
Test DAG/Plan memory leak - accumulation in continuation loops
"""
import asyncio
import gc
from web_agent.core.task import Task, TaskDAG, TaskStatus
from web_agent.planning.plan_structures import StructuredPlan, Step, StepType
from web_agent.planning.dag_converter import PlanToDAGConverter
from web_agent.util.memory_monitor import get_memory_monitor

async def test_dag_memory():
    print("="*60)
    print("MEMORY TEST: DAG/Plan accumulation")
    print("="*60)
    
    mem_monitor = get_memory_monitor()
    mem_monitor.set_baseline()
    mem_monitor.log_ram("Baseline")
    
    # Test 1: Create multiple Plans without cleanup (simulates continuation loop)
    print("\n--- Test 1: Create 20 Plans WITHOUT cleanup ---")
    plans_list = []
    for i in range(20):
        # Create a plan with 5 steps
        steps = []
        for j in range(5):
            step = Step(
                number=j+1,
                name=f"Step {j+1} of plan {i}",
                description=f"Detailed description of step {j+1} in plan {i}",
                type=StepType.DIRECT if j % 2 == 0 else StepType.DELEGATE,
                dependencies=[j] if j > 0 else [],
                estimated_time_seconds=30
            )
            steps.append(step)
        
        plan = StructuredPlan(
            goal=f"Test plan {i}",
            steps=steps,
            complexity="moderate",
            estimated_total_time=150
        )
        plans_list.append(plan)
        
        if i % 5 == 0:
            mem_monitor.log_ram(f"After creating {i+1} plans")
    
    mem_monitor.log_ram("After creating 20 plans (before cleanup)")
    
    # Clear and GC
    plans_list.clear()
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After clearing plans")
    
    # Test 2: Create DAGs from Plans without cleanup
    print("\n--- Test 2: Create 20 DAGs WITHOUT cleanup ---")
    dags_list = []
    for i in range(20):
        # Create a plan
        steps = []
        for j in range(5):
            step = Step(
                number=j+1,
                name=f"Step {j+1} of DAG plan {i}",
                description=f"Description for DAG step {j+1} in plan {i}",
                type=StepType.DIRECT,
                dependencies=[j] if j > 0 else [],
                estimated_time_seconds=20
            )
            steps.append(step)
        
        plan = StructuredPlan(
            goal=f"DAG test plan {i}",
            steps=steps,
            complexity="simple",
            estimated_total_time=100
        )
        
        # Convert to DAG
        dag = PlanToDAGConverter.convert(plan)
        dags_list.append(dag)
        
        # Don't delete plan immediately (simulate leak)
        if i % 5 == 0:
            mem_monitor.log_ram(f"After creating {i+1} DAGs")
    
    mem_monitor.log_ram(f"After creating 20 DAGs (before cleanup)")
    
    # Clear and GC
    dags_list.clear()
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After clearing DAGs")
    
    # Test 3: Simulate continuation loop (create new plan/DAG, delete old)
    print("\n--- Test 3: Continuation loop with cleanup ---")
    current_dag = None
    current_plan = None
    
    for i in range(15):
        # Delete old plan and DAG first
        if current_plan is not None:
            del current_plan
        if current_dag is not None:
            del current_dag
        gc.collect()
        
        # Create new plan
        steps = []
        for j in range(7):
            step = Step(
                number=j+1,
                name=f"Continuation step {j+1}",
                description=f"Step {j+1} in continuation iteration {i}",
                type=StepType.DIRECT,
                dependencies=[],
                estimated_time_seconds=15
            )
            steps.append(step)
        
        current_plan = StructuredPlan(
            goal=f"Continuation iteration {i}",
            steps=steps,
            complexity="simple",
            estimated_total_time=105
        )
        current_dag = PlanToDAGConverter.convert(current_plan)
        
        # Delete plan immediately after DAG creation
        del current_plan
        gc.collect()
        current_plan = None
        
        if i % 5 == 0:
            mem_monitor.log_ram(f"Continuation iteration {i+1}")
    
    # Final cleanup
    if current_dag:
        del current_dag
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After continuation loop cleanup")
    
    # Test 4: Task objects accumulation
    print("\n--- Test 4: Task objects in DAG ---")
    dag = TaskDAG()
    
    # Add 100 tasks
    for i in range(100):
        task = Task(
            id=f"task_{i}",
            description=f"Task {i} description with some metadata",
            dependencies=[f"task_{i-1}"] if i > 0 else [],
            status=TaskStatus.PENDING
        )
        dag.add_task(task)
        
        if i % 25 == 0:
            mem_monitor.log_ram(f"After adding {i+1} tasks to DAG")
    
    mem_monitor.log_ram("After adding 100 tasks (before cleanup)")
    
    # Clear DAG
    del dag
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("After deleting DAG with 100 tasks")
    
    # Final cleanup
    gc.collect()
    gc.collect()
    mem_monitor.log_ram("Final cleanup")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_dag_memory())
