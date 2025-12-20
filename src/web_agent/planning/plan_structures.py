"""
Data structures for task planning.
"""
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class StepType(Enum):
    """Type of plan step"""
    DIRECT = "direct"      # Execute directly
    DELEGATE = "delegate"  # Delegate to sub-agent

@dataclass
class Step:
    """
    Single step in a structured plan.
    """
    number: int
    name: str
    description: str
    type: StepType
    dependencies: List[int] = field(default_factory=list)
    estimated_time_seconds: int = 10
    can_run_parallel: bool = False
    fallback_strategy: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Step':
        """Create Step from dict"""
        return cls(
            number=data['number'],
            name=data['name'],
            description=data['description'],
            type=StepType(data.get('type', 'direct')),
            dependencies=data.get('dependencies', []),
            estimated_time_seconds=data.get('estimated_time_seconds', 10),
            can_run_parallel=len(data.get('dependencies', [])) == 0,
            fallback_strategy=data.get('fallback_strategy')
        )
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            'number': self.number,
            'name': self.name,
            'description': self.description,
            'type': self.type.value,
            'dependencies': self.dependencies,
            'estimated_time_seconds': self.estimated_time_seconds,
            'can_run_parallel': self.can_run_parallel,
            'fallback_strategy': self.fallback_strategy
        }

@dataclass
class StructuredPlan:
    """
    Complete structured plan for accomplishing a goal.
    """
    goal: str
    steps: List[Step]
    complexity: str  # simple, moderate, complex
    estimated_total_time: int
    metadata: dict = field(default_factory=dict)
    
    @classmethod
    def from_gemini_output(cls, goal: str, plan_data: dict) -> 'StructuredPlan':
        steps = [Step.from_dict(step_data) for step_data in plan_data.get('steps', [])]
        return cls(
            goal=goal,
            steps=steps,
            complexity=plan_data.get('complexity', 'simple'),
            estimated_total_time=plan_data.get('estimated_total_time', 0),
            metadata={
                'created_at': plan_data.get('created_at'),
                'starting_url': plan_data.get('starting_url')
            }
        )
    
    def get_step(self, number: int) -> Optional[Step]:
        for step in self.steps:
            if step.number == number:
                return step
        return None
    
    def get_independent_steps(self) -> List[Step]:
        return [step for step in self.steps if not step.dependencies]
    
    def get_total_steps(self) -> int:
        return len(self.steps)
    
    def to_dict(self) -> dict:
        return {
            'goal': self.goal,
            'steps': [step.to_dict() for step in self.steps],
            'complexity': self.complexity,
            'estimated_total_time': self.estimated_total_time,
            'metadata': self.metadata
        }
    
    def __str__(self) -> str:
        lines = [
            f"\n{'='*60}",
            f"Plan: {self.goal}",
            f"{'='*60}",
            f"Complexity: {self.complexity}",
            f"Total Steps: {len(self.steps)}",
            f"Estimated Time: {self.estimated_total_time}s",
            f"\nSteps:"
        ]
        for step in self.steps:
            dep_str = f" (depends on: {step.dependencies})" if step.dependencies else ""
            lines.append(f"  {step.number}. {step.name}{dep_str}")
            lines.append(f"     {step.description}")
            lines.append(f"     Type: {step.type.value}, Est: {step.estimated_time_seconds}s")
        lines.append(f"{'='*60}\n")
        return "\n".join(lines)
