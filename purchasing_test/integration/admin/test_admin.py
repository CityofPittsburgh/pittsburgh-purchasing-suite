# -*- coding: utf-8 -*-

from flask import current_app
from purchasing_test.test_base import BaseTestCase
from purchasing_test.util import insert_a_user, insert_a_role

class TestAdmin(BaseTestCase):
    render_templates = False

    def setUp(self):
        super(TestAdmin, self).setUp()
        self.email = 'foo@foo.com'
        self.email2 = 'bar@foo.com'
        self.admin_role = insert_a_role('admin')
        self.superadmin_role = insert_a_role('superadmin')
        self.admin_user = insert_a_user(email=self.email, role=self.admin_role)
        self.superadmin_user = insert_a_user(email=self.email2, role=self.superadmin_role)

    def test_no_role_access(self):
        # test that it properly redirects to the login page for anonymous users
        request = self.client.get('/admin/')
        self.assertEquals(request.status_code, 403)
        # test that a specific view renders properly
        request = (self.client.get('/admin/user/'))
        self.assertEquals(request.status_code, 403)

    def test_admin_role_access(self):
        # test that it works properly for admin users
        self.login_user(self.admin_user)
        request = self.client.get('/admin/')
        self.assert200(request)

        # test that admins can't access the roles admin view
        request = self.client.get('/admin/role/')
        self.assertEquals(request.status_code, 403)

    def test_superadmin_role_access(self):
        # test that it works properly for superadmin users
        self.login_user(self.superadmin_user)
        self.assert200(self.client.get('/admin/'))
        self.assert200(self.client.get('/admin/role/'))
        self.assert200(self.client.get('/admin/user-roles/'))

    def test_admin_views(self):
        self.login_user(self.superadmin_user)

        for rule in current_app.url_map.iter_rules():
            if not rule.rule.startswith('/admin') or \
                'ajax' in rule.rule or \
                'GET' not in rule.methods or \
                'static' in rule.rule:
                    continue
            else:
                code = self.client.get(rule.rule).status_code
                self.assertTrue(code in [200, 302])
