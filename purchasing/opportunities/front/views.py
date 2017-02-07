# -*- coding: utf-8 -*-

import datetime

from flask import (
    render_template, request, current_app, flash,
    redirect, url_for, session, abort
)
from flask_security import current_user

from purchasing.database import db
from purchasing.notifications import Notification
from purchasing.opportunities.forms import UnsubscribeForm, VendorSignupForm, OpportunitySignupForm
from purchasing.opportunities.models import Category, Opportunity, Vendor

from purchasing.opportunities.front import blueprint
from purchasing.opportunities.util import init_form, signup_for_opp

from purchasing.users.models import User, Role

@blueprint.route('/')
def splash():
    '''Landing page for opportunities site

    :status 200: Successfully render the splash page
    '''
    current_app.logger.info('BEACON FRONT SPLASH VIEW')
    return render_template(
        'opportunities/front/splash.html'
    )

@blueprint.route('/manage', methods=['GET', 'POST'])
def manage():
    '''Manage a vendor's signups

    :status 200: render the
        :py:class:`~purchasing.opportunities.forms.UnsubscribeForm`
    :status 302: post the
        :py:class:`~purchasing.opportunities.forms.UnsubscribeForm`
        and change the user's email subscriptions and redirect them
        back to the management page.
    '''
    form = init_form(UnsubscribeForm)
    form_categories = []
    form_opportunities = []
    vendor = None

    if form.validate_on_submit():
        email = form.data.get('email')
        vendor = Vendor.query.filter(Vendor.email == email).first()

        if vendor is None:
            current_app.logger.info(
                'OPPMANAGEVIEW - Unsuccessful search for email {}'.format(email)
            )
            form.email.errors = ['We could not find the email {}'.format(email)]

        if request.form.get('button', '').lower() == 'update email preferences':
            remove_categories = set([Category.query.get(i) for i in form.categories.data])
            remove_opportunities = set([Opportunity.query.get(i) for i in form.opportunities.data])

            # remove none types if any
            remove_categories.discard(None)
            remove_opportunities.discard(None)

            vendor.categories = vendor.categories.difference(remove_categories)
            vendor.opportunities = vendor.opportunities.difference(remove_opportunities)
            if form.data.get('subscribed_to_newsletter'):
                vendor.subscribed_to_newsletter = False

            current_app.logger.info(
                u'''OPPMANAGEVIEW - Vendor {} unsubscribed from:
                Categories: {}
                Opportunities: {}
                Subscribed from newsletter: {}
                '''.format(
                    email,
                    u', '.join([i.category_friendly_name for i in remove_categories if remove_categories and len(remove_categories) > 0]),
                    u', '.join([i.description for i in remove_opportunities if remove_opportunities and len(remove_opportunities) > 0]),
                    vendor.subscribed_to_newsletter
                )
            )

            db.session.commit()
            flash('Preferences updated!', 'alert-success')

        if vendor:
            for subscription in vendor.categories:
                form_categories.append((subscription.id, subscription.category_friendly_name))
            for subscription in vendor.opportunities:
                form_opportunities.append((subscription.id, subscription.title))

    form = init_form(UnsubscribeForm)
    form.opportunities.choices = form_opportunities
    form.categories.choices = form_categories
    return render_template(
        'opportunities/front/manage.html', form=form,
        vendor=vendor if vendor else Vendor()
    )

@blueprint.route('/opportunities', methods=['GET', 'POST'])
def browse():
    '''Browse available opportunities

    :status 200: render the browse template page
    :status 302: subscribe to one or multiple opportunities via
        the :py:class:`~purchasing.opportunities.forms.OpportunitySignupForm`
    '''
    _open, upcoming = [], []

    signup_form = init_form(OpportunitySignupForm)
    if signup_form.validate_on_submit():
        opportunities = request.form.getlist('opportunity')
        if signup_for_opp(
            signup_form, opportunity=opportunities, multi=True
        ):
            flash('Successfully subscribed for updates!', 'alert-success')
            return redirect(url_for('opportunities.browse'))

    opportunities = Opportunity.query.filter(
        Opportunity.planned_submission_end >= datetime.date.today()
    ).all()

    for opportunity in opportunities:
        if opportunity.is_submission_start:
            _open.append(opportunity)
        elif opportunity.is_upcoming:
            upcoming.append(opportunity)

    current_app.logger.info('BEACON FRONT OPEN OPPORTUNITY VIEW')
    return render_template(
        'opportunities/browse.html', opportunities=opportunities,
        current_user=current_user, signup_form=signup_form,
        _open=sorted(_open, key=lambda i: i.planned_submission_end),
        upcoming=sorted(upcoming, key=lambda i: i.planned_submission_start),
        session_vendor=session.get('email')
    )

@blueprint.route('/opportunities/expired', methods=['GET'])
def expired():
    '''View expired contracts

    :status 200: render the expired opportunities templates
    '''
    expired = Opportunity.query.filter(
        Opportunity.planned_submission_end < datetime.date.today(),
        Opportunity.is_public == True
    ).all()

    current_app.logger.info('BEACON FRONT CLOSED OPPORTUNITY VIEW')

    return render_template(
        'opportunities/front/expired.html', expired=expired
    )

@blueprint.route('/opportunities/<int:opportunity_id>', methods=['GET', 'POST'])
def detail(opportunity_id):
    '''View one opportunity in detail

    :status 200: Render the opportunity's detail template
    :status 302: Signup for this particular opportunity via the
        :py:class:`~purchasing.opportunities.forms.OpportunitySignupForm`
    '''
    opportunity = Opportunity.query.get(opportunity_id)
    if opportunity and opportunity.can_view(current_user):
        signup_form = init_form(OpportunitySignupForm)
        if signup_form.validate_on_submit():
            signup_success = signup_for_opp(signup_form, opportunity)
            if signup_success:
                flash('Successfully subscribed for updates!', 'alert-success')
                return redirect(url_for('opportunities.detail', opportunity_id=opportunity.id))

        current_app.logger.info(u'BEACON FRONT OPPORTUNITY DETAIL VIEW | Opportunity {} (ID: {})'.format(
            opportunity.title, opportunity.id
        ))

        return render_template(
            'opportunities/front/detail.html', opportunity=opportunity,
            current_user=current_user, signup_form=signup_form,
        )
    abort(404)
