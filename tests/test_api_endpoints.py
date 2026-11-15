import pytest
from rest_framework.test import APIClient
from unittest.mock import patch
from apps.analysis.models import Website, AnalysisJob, WorkflowState

@pytest.mark.django_db
class TestApiEndpoints:

    def setup_method(self):
        self.client = APIClient()

    def test_health_endpoints(self):
        resp_live = self.client.get('/health/live/')
        assert resp_live.status_code == 200
        assert resp_live.json()['status'] == 'healthy'

        resp_ready = self.client.get('/health/ready/')
        assert resp_ready.status_code == 200
        assert resp_ready.json()['status'] == 'ready'

        resp_detail = self.client.get('/health/')
        assert resp_detail.status_code == 200
        assert 'components' in resp_detail.json()

    def test_submit_analysis_invalid_url(self):
        response = self.client.post('/api/v1/website-analysis/', {
            "url": "not-a-valid-url"
        }, format='json')
        assert response.status_code == 400

    @patch('apps.workflow.manager.execute_analysis_workflow_task.delay')
    def test_submit_analysis_success(self, mock_celery_delay):
        response = self.client.post('/api/v1/website-analysis/', {
            "url": "https://valid-company-example.com",
            "objective": "company_intelligence",
            "options": {"sync": False}
        }, format='json')

        assert response.status_code == 202
        data = response.json()
        assert 'id' in data
        assert data['status'] == 'PENDING'
        assert data['domain'] == 'valid-company-example.com'

        # Query GET detail
        job_id = data['id']
        detail_resp = self.client.get(f'/api/v1/website-analysis/{job_id}/')
        assert detail_resp.status_code == 200
        assert detail_resp.json()['id'] == job_id

    def test_dashboard_ui_endpoint(self):
        response = self.client.get('/crawler-dashboard/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Aura Intel' in content
        assert 'Target Intelligence Console' in content
        assert 'dashboard.css' in content
        assert 'dashboard.js' in content
        assert 'DJANGO_DATA' in content

