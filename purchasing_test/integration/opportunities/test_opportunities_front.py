# -*- coding: utf-8 -*-

import json
import datetime
from flask import current_app, url_for
from werkzeug.datastructures import MultiDict

from purchasing.extensions import mail, db
from purchasing.opportunities.models import Vendor, Category

from purchasing_test.util import insert_a_role, insert_a_user, insert_an_opportunity

from purchasing_test.integration.opportunities.test_opportunities_base import (
    TestOpportunitiesFrontBase, TestOpportunitiesAdminBase
)

class TestOpportunities(TestOpportunitiesFrontBase):
    render_templates = True

    def test_templates(self):
        # insert our opportunity, users
        admin_role = insert_a_role('admin')
        admin = insert_a_user(role=admin_role)

        opportunity = insert_an_opportunity(
            contact=admin, created_by=admin,
            is_public=True, planned_publish=datetime.date.today() - datetime.timedelta(1),
            planned_submission_start=datetime.date.today() + datetime.timedelta(2),
            planned_submission_end=datetime.datetime.today() + datetime.timedelta(2)
        )

        for rule in current_app.url_map.iter_rules():

            _endpoint = rule.endpoint.split('.')
            # filters out non-beacon endpoints
            if (len(_endpoint) > 1 and _endpoint[1] == 'static') or \
                _endpoint[0] != ('opportunities', 'opportunities_admin'):
                    continue
            else:
                if '<int:' in rule.rule:
                    response = self.client.get(url_for(rule.endpoint, opportunity_id=opportunity.id))
                else:
                    response = self.client.get(rule.rule)
                self.assert200(response)

    def test_index(self):
        response = self.client.get('/beacon/')
        self.assert200(response)
        self.assert_template_used('opportunities/front/splash.html')


    def test_manage_subscriptions(self):
        v = Vendor.create(
            email='foo2@foo.com', business_name='foo', subscribed_to_newsletter=True
        )

        for i in Category.query.filter(Category.id.in_([1,2,3])):
            v.categories.add(i)
        db.session.commit()

        manage = self.client.post('/beacon/manage', data=dict(
            email='foo2@foo.com'
        ))

        self.assert200(manage)
        form = self.get_context_variable('form')
        self.assertEquals(len(form.categories.choices), 3)

        # it shouldn't unsubscribe you if you click the wrong button
        not_unsub_button = self.client.post('/beacon/manage', data=dict(
            email='foo2@foo.com',
            categories=[1, 2],
        ))

        self.assert200(not_unsub_button)
        form = self.get_context_variable('form')
        self.assertEquals(len(form.categories.choices), 3)

        unsubscribe = self.client.post('/beacon/manage', data=dict(
            email='foo2@foo.com',
            categories=[1, 2],
            button='Update email preferences'
        ))

        self.assert200(unsubscribe)
        form = self.get_context_variable('form')
        self.assertEquals(len(form.categories.choices), 1)

        # it shouldn't matter if you somehow unsubscribe from things
        # you are accidentally subscribed to
        unsubscribe_all = self.client.post('/beacon/manage', data=dict(
            email='foo2@foo.com',
            categories=[3, 5, 6],
            button='Update email preferences',
            subscribed_to_newsletter=False
        ))

        self.assert200(unsubscribe_all)
        self.assertTrue('You are not subscribed to anything!' in unsubscribe_all.data)

class TestOpportunitiesSubscriptions(TestOpportunitiesAdminBase):
    def test_signup_for_multiple_opportunities(self):
        self.assertEquals(Vendor.query.count(), 1)
        # duplicates should get filtered out
        post = self.client.post('/beacon/opportunities', data=MultiDict([
            ('email', 'new@foo.com'), ('business_name', 'foo'),
            ('opportunity', str(self.opportunity3.id)),
            ('opportunity', str(self.opportunity4.id)),
            ('opportunity', str(self.opportunity3.id)),
            ('opportunity', str(self.opportunity1.id))
        ]))

        self.assertEquals(Vendor.query.count(), 2)

        # should subscribe that vendor to the opportunity
        self.assertEquals(len(Vendor.query.filter(Vendor.email == 'new@foo.com').first().opportunities), 3)
        for i in Vendor.query.get(1).opportunities:
            self.assertTrue(i.id in [self.opportunity1.id, self.opportunity3.id, self.opportunity4.id])

        # should redirect and flash properly
        self.assertEquals(post.status_code, 302)
        self.assert_flashes('Successfully subscribed for updates!', 'alert-success')

    def test_unicode_get(self):
        self.login_user(self.admin)
        self.assert200(self.client.get('/beacon/opportunities/{}'.format(self.opportunity1.id)))

    def test_signup_for_opportunity(self):
        self.opportunity1.is_public = True
        self.opportunity1.planned_publish = datetime.date.today() - datetime.timedelta(2)
        db.session.commit()

        with mail.record_messages() as outbox:
            self.assertEquals(Vendor.query.count(), 1)
            post = self.client.post('/beacon/opportunities/{}'.format(self.opportunity1.id), data={
                'email': 'new@foo.com', 'business_name': 'foo'
            })
            # should create a new vendor
            self.assertEquals(Vendor.query.count(), 2)

            # should subscribe that vendor to the opportunity
            self.assertEquals(len(Vendor.query.filter(Vendor.email == 'new@foo.com').first().opportunities), 1)
            self.assertTrue(
                self.opportunity1.id in [
                    i.id for i in Vendor.query.filter(Vendor.email == 'new@foo.com').first().opportunities
                ]
            )

            # should redirect and flash properly
            self.assertEquals(post.status_code, 302)
            self.assert_flashes('Successfully subscribed for updates!', 'alert-success')

            self.assertEquals(len(outbox), 1)

    def test_signup_for_opportunity_session(self):
        self.client.post('/beacon/opportunities', data={
            'business_name': 'NEW NAME',
            'email': 'new@foo.com',
            'opportunity': self.opportunity2.id
        })

        self.assertEquals(Vendor.query.count(), 2)
        self.assertEquals(len(Vendor.query.filter(Vendor.email == 'new@foo.com').first().opportunities), 1)

        with self.client.session_transaction() as session:
            self.assertEquals(session['email'], 'new@foo.com')
            self.assertEquals(session['business_name'], 'NEW NAME')
