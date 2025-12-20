"""
Unit tests for WorkerMemory.
"""
import pytest
from web_agent.storage.worker_memory import WorkerMemory


def test_memory_initialization():
    """Test memory initialization"""
    memory = WorkerMemory(namespace="test_worker")
    assert memory.namespace == "test_worker"
    assert len(memory.get_all()) == 0


def test_store_and_retrieve():
    """Test storing and retrieving values"""
    memory = WorkerMemory(namespace="test_worker")
    
    memory.store("key1", "value1")
    memory.store("key2", {"nested": "data"})
    memory.store("key3", [1, 2, 3])
    
    assert memory.retrieve("key1") == "value1"
    assert memory.retrieve("key2") == {"nested": "data"}
    assert memory.retrieve("key3") == [1, 2, 3]


def test_retrieve_default():
    """Test retrieving with default value"""
    memory = WorkerMemory(namespace="test_worker")
    
    assert memory.retrieve("nonexistent", default="default_value") == "default_value"
    assert memory.retrieve("nonexistent") is None


def test_exists():
    """Test checking if key exists"""
    memory = WorkerMemory(namespace="test_worker")
    
    memory.store("existing_key", "value")
    
    assert memory.exists("existing_key")
    assert not memory.exists("nonexistent_key")


def test_delete():
    """Test deleting keys"""
    memory = WorkerMemory(namespace="test_worker")
    
    memory.store("key1", "value1")
    assert memory.exists("key1")
    
    success = memory.delete("key1")
    assert success
    assert not memory.exists("key1")
    
    # Deleting non-existent key
    success = memory.delete("key1")
    assert not success


def test_get_all():
    """Test getting all values"""
    memory = WorkerMemory(namespace="test_worker")
    
    memory.store("key1", "value1")
    memory.store("key2", "value2")
    memory.store("key3", "value3")
    
    all_data = memory.get_all()
    assert len(all_data) == 3
    assert all_data["key1"] == "value1"
    assert all_data["key2"] == "value2"
    assert all_data["key3"] == "value3"


def test_clear():
    """Test clearing all data"""
    memory = WorkerMemory(namespace="test_worker")
    
    memory.store("key1", "value1")
    memory.store("key2", "value2")
    
    assert len(memory.get_all()) == 2
    
    memory.clear()
    assert len(memory.get_all()) == 0


def test_namespace_isolation():
    """Test that different namespaces are isolated"""
    memory1 = WorkerMemory(namespace="worker1")
    memory2 = WorkerMemory(namespace="worker2")
    
    memory1.store("shared_key", "value1")
    memory2.store("shared_key", "value2")
    
    assert memory1.retrieve("shared_key") == "value1"
    assert memory2.retrieve("shared_key") == "value2"
    
    # Clearing one shouldn't affect the other
    memory1.clear()
    assert memory1.retrieve("shared_key") is None
    assert memory2.retrieve("shared_key") == "value2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
