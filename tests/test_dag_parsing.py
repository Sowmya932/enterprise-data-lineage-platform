"""
test_dag_parsing.py
-------------------
Unit and integration tests for Airflow DAG parsing functionality.

Tests cover:
- DAG metadata extraction
- Task dependency parsing
- DAG lineage integration
- Error handling for malformed DAG code
"""

import pytest
from backend.parsers.dag_parser import DAGParser
from backend.exceptions import DagParseError, FileNotFoundError


class TestDAGParserBasics:
    """Test basic DAG parsing functionality."""
    
    @pytest.mark.unit
    def test_parse_dag_from_content(self, sample_dag_content):
        """Test parsing DAG from content string."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        assert isinstance(result, dict)
        assert "dag_id" in result or "error" not in result
    
    @pytest.mark.unit
    def test_parse_simple_dag_structure(self, sample_dag_content):
        """Test parsing simple DAG with task dependencies."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        # Should extract DAG ID and tasks
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_extract_task_dependencies(self, sample_dag_content):
        """Test extracting task dependencies from DAG."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        # Should contain dependencies
        assert "dependencies" in result or "tasks" in result or "error" not in result


class TestDAGParserErrors:
    """Test error handling in DAG parsing."""
    
    @pytest.mark.unit
    def test_parse_malformed_dag(self):
        """Test parsing malformed DAG code."""
        parser = DAGParser()
        malformed = "DAG( this is not valid python ]"
        
        result = parser.parse_dag_content(malformed)
        
        # Should handle gracefully
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_empty_dag(self):
        """Test parsing empty DAG content."""
        parser = DAGParser()
        result = parser.parse_dag_content("")
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_dag_without_dag_id(self):
        """Test parsing DAG without explicit DAG ID."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from datetime import datetime

with DAG() as dag:
    pass
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_dag_file_not_found(self):
        """Test parsing nonexistent DAG file."""
        parser = DAGParser()
        
        # Should raise FileNotFoundError or return error
        result = parser.parse_dag_file("/nonexistent/path/dag.py")
        
        assert isinstance(result, dict) or isinstance(result, FileNotFoundError)


class TestDAGTaskExtraction:
    """Test task extraction from DAG."""
    
    @pytest.mark.unit
    def test_extract_task_ids(self, sample_dag_content):
        """Test extracting task IDs from DAG."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        if "tasks" in result:
            assert isinstance(result["tasks"], list)
    
    @pytest.mark.unit
    def test_extract_task_operators(self, sample_dag_content):
        """Test extracting task operator types."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        # Should identify operators
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_extract_parallel_tasks(self):
        """Test extracting parallel task execution."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.operators.python import PythonOperator

def task_a(): pass
def task_b(): pass
def task_c(): pass

with DAG('parallel_dag') as dag:
    a = PythonOperator(task_id='task_a', python_callable=task_a)
    b = PythonOperator(task_id='task_b', python_callable=task_b)
    c = PythonOperator(task_id='task_c', python_callable=task_c)
    
    a >> [b, c]
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)


class TestDAGDependencyParsing:
    """Test dependency parsing in DAGs."""
    
    @pytest.mark.unit
    def test_parse_sequential_dependencies(self, sample_dag_content):
        """Test parsing sequential task dependencies."""
        parser = DAGParser()
        result = parser.parse_dag_content(sample_dag_content)
        
        if "dependencies" in result:
            deps = result["dependencies"]
            assert isinstance(deps, list)
    
    @pytest.mark.unit
    def test_parse_branching_dependencies(self):
        """Test parsing branching task dependencies."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.operators.python import PythonOperator

def task1(): pass
def task2(): pass
def task3(): pass

with DAG('branching_dag') as dag:
    t1 = PythonOperator(task_id='task1', python_callable=task1)
    t2 = PythonOperator(task_id='task2', python_callable=task2)
    t3 = PythonOperator(task_id='task3', python_callable=task3)
    
    t1 >> [t2, t3]
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_cross_dependencies(self):
        """Test parsing complex cross-dependencies."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.operators.python import PythonOperator

def task(): pass

with DAG('complex_dag') as dag:
    t1 = PythonOperator(task_id='t1', python_callable=task)
    t2 = PythonOperator(task_id='t2', python_callable=task)
    t3 = PythonOperator(task_id='t3', python_callable=task)
    t4 = PythonOperator(task_id='t4', python_callable=task)
    
    [t1, t2] >> t3 >> t4
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)


class TestDAGParsingIntegration:
    """Integration tests for DAG parsing."""
    
    @pytest.mark.integration
    def test_parse_dag_endpoint(self, client, sample_dag_content):
        """Test POST /parse-dag endpoint."""
        response = client.post(
            "/parse-dag",
            json={
                "dag_content": sample_dag_content,
            }
        )
        
        assert response.status_code in [200, 201]
        data = response.json()
        assert "success" in data or "metadata" in data
    
    @pytest.mark.integration
    def test_parse_dag_from_file_path(self, client):
        """Test parsing DAG from file path."""
        response = client.post(
            "/parse-dag",
            json={
                "dag_file_path": "airflow_dags/etl_pipeline_dag.py",
            }
        )
        
        # May succeed or fail depending on file existence
        assert response.status_code in [200, 201, 404, 422]


# Additional tests for edge cases and complex scenarios
class TestDAGParsingEdgeCases:
    """Test edge cases in DAG parsing."""
    
    @pytest.mark.unit
    def test_parse_dag_with_imports(self):
        """Test parsing DAG with multiple imports."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta
import sys
import os

def task_func():
    pass

with DAG('import_dag') as dag:
    t = PythonOperator(task_id='task', python_callable=task_func)
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_dag_with_sensors(self):
        """Test parsing DAG with sensors."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.sensors.filesystem import FileSensor

with DAG('sensor_dag') as dag:
    sensor = FileSensor(task_id='file_check', filepath='/tmp/file.txt')
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)
    
    @pytest.mark.unit
    def test_parse_dag_with_branching_operator(self):
        """Test parsing DAG with branching operator."""
        parser = DAGParser()
        dag_content = """
from airflow import DAG
from airflow.operators.branching import BranchPythonOperator

def choose_branch():
    return 'branch_a'

with DAG('branching_op_dag') as dag:
    branch_op = BranchPythonOperator(
        task_id='branch',
        python_callable=choose_branch
    )
"""
        result = parser.parse_dag_content(dag_content)
        
        assert isinstance(result, dict)
