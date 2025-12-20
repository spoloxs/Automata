"""
Converts StructuredPlan to TaskDAG.
"""
from web_agent.planning.plan_structures import StructuredPlan, StepType
from web_agent.core.task import Task, TaskDAG, TaskPriority

class PlanToDAGConverter:
    """Converts StructuredPlan to TaskDAG"""
    @staticmethod
    def convert(plan: StructuredPlan) -> TaskDAG:
        dag = TaskDAG()
        step_to_task_id = {}
        print(f"📊 Converting plan to DAG ({len(plan.steps)} steps)...")
        for step in plan.steps:
            if step.type == StepType.DELEGATE:
                priority = TaskPriority.HIGH
            elif len(step.dependencies) == 0:
                priority = TaskPriority.HIGH
            else:
                priority = TaskPriority.NORMAL
            task = Task(
                description=step.description,
                dependencies=[],
                metadata={
                    'step_number': step.number,
                    'step_name': step.name,
                    'step_type': step.type.value,
                    'estimated_time': step.estimated_time_seconds,
                    'can_parallel': step.can_run_parallel,
                    'fallback_strategy': step.fallback_strategy,
                },
                priority=priority
            )
            dag.add_task(task)
            step_to_task_id[step.number] = task.id
            print(f"   ✅ Task {step.number}: {step.name} ({task.id[:8]})")
        for step in plan.steps:
            if step.dependencies:
                task_id = step_to_task_id[step.number]
                task = dag.get_task(task_id)
                for dep_step_num in step.dependencies:
                    dep_task_id = step_to_task_id[dep_step_num]
                    dag.add_dependency(task_id, dep_task_id)
                    task.dependencies.append(dep_task_id)
                print(f"   🔗 Task {step.number} depends on {step.dependencies}")
        print(f"   ⚡ DAG conversion complete")
        return dag
