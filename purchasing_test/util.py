# -*- coding: utf-8 -*-

import datetime
from purchasing.database import db
from sqlalchemy.exc import IntegrityError

from purchasing.data.contracts import ContractBase
from purchasing.data.stages import Stage
from purchasing.data.flows import Flow

from purchasing.users.models import Role, User
from purchasing_test.factories import (
    UserFactory, RoleFactory, StageFactory, FlowFactory, DepartmentFactory,
    ContractBaseFactory, ContractPropertyFactory,
    CompanyFactory, OpportunityFactory, RequiredBidDocumentFactory
)

def insert_a_contract(properties=None, **kwargs):
    contract_data = dict(
        description='test2',
    ) if not kwargs else dict(kwargs)

    contract = ContractBaseFactory.create(**contract_data)

    if properties:
        [i.update({'contract': contract}) for i in properties]
    else:
        properties = [
            dict(contract=contract, key='foo', value='bar'),
            dict(contract=contract, key='baz', value='qux')
        ]

    for _property in properties:
        ContractPropertyFactory.create(**_property)
    return contract

def get_a_property():
    contract = ContractBase.query.first()
    if not contract:
        contract = insert_a_contract()

    return contract.properties[0]

def insert_a_stage(name='foo', send_notifs=False, post_opportunities=False, default_message=''):
    stage = StageFactory.create(**{
        'name': name,
        'post_opportunities': post_opportunities,
        'default_message': default_message
    })

    return stage

def get_a_stage_property():
    stage = Stage.query.first()
    if not stage:
        stage = insert_a_stage()

    return stage.properties.first()

def insert_a_flow(name='test', stage_ids=None):
    try:
        flow = FlowFactory.create(**{
            'flow_name': name,
            'stage_order': stage_ids
        })

        return flow
    except IntegrityError:
        db.session.rollback()
        return Flow.query.filter(Flow.name == name).first()

def insert_a_company(name='test company', insert_contract=True):
    if insert_contract:
        contract = insert_a_contract()
        company = CompanyFactory.create(**{
            'company_name': name,
            'contracts': [contract]
        })
    else:
        company = CompanyFactory.create(**{'company_name': name})

    return company

def create_a_user(email='foo@foo.com', department='Other', role=None):
    return UserFactory(
        email=email, first_name='foo', last_name='foo',
        department=DepartmentFactory.create(name=department), role=role
    )

def insert_a_user(email=None, department=None, role=None, pw='password'):
    role = role if role else RoleFactory.create()
    try:
        if email:
            user = UserFactory.create(
                email=email, roles=[role], department=department,
                confirmed_at=datetime.datetime.now(),
                password=pw
            )
        else:
            user = UserFactory.create(
                roles=[role], department=department,
                password=pw, confirmed_at=datetime.datetime.now()
            )
        return user
    except IntegrityError:
        db.session.rollback()
        return User.query.filter(User.email == email).first()

def insert_a_role(name):
    try:
        role = RoleFactory.create(name=name)
        return role
    except IntegrityError:
        db.session.rollback()
        return Role.query.filter(Role.name == name).first()

def get_a_role(name):
    return Role.query.filter(Role.name == name).first()

def insert_a_document(name='Foo', description='Bar'):
    document = RequiredBidDocumentFactory.create(**dict(
        display_name=name, description=description
    ))
    document.save()

    return document

def insert_an_opportunity(
    contact=None, department=None,
    title='Test', description='Test',
    planned_publish=datetime.datetime.today(),
    planned_submission_start=datetime.datetime.today(),
    planned_submission_end=datetime.datetime.today() + datetime.timedelta(1),
    required_documents=[], categories=set(), documents=[],
    created_from_id=None, created_by=None, is_public=True, is_archived=False
):
    department = department if department else DepartmentFactory()
    opportunity = OpportunityFactory.create(**dict(
        department_id=department.id, contact=contact, title=title,
        description=description, planned_publish=planned_publish,
        planned_submission_start=planned_submission_start,
        planned_submission_end=planned_submission_end,
        created_from_id=created_from_id, created_by=created_by,
        created_by_id=created_by.id, vendor_documents_needed=documents,
        is_public=is_public, is_archived=is_archived, categories=categories
    ))

    return opportunity
