# -*- coding:utf-8 -*-

# Add the tests main directory into the path, to be able to load things from base
import os
import sys
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), '..')))

import unittest

from limpyd import fields
from limpyd.exceptions import *
from limpyd.contrib.related import (RelatedModel,
                                    FKStringField, FKHashableField, M2MSetField,
                                    M2MListField, M2MSortedSetField)

from base import LimpydBaseTest


class TestRedisModel(RelatedModel):
    """
    Use it as a base for all RelatedModel created for tests
    """
    database = LimpydBaseTest.database
    abstract = True
    namespace = "related-tests"


class Person(TestRedisModel):
    name = fields.PKField()
    prefered_group = FKStringField('Group')


class Group(TestRedisModel):
    name = fields.PKField()
    owner = FKHashableField(Person, related_name='owned_groups')
    parent = FKStringField('self', related_name='children')
    members = M2MSetField(Person, related_name='membership')


class RelatedToTest(LimpydBaseTest):
    """ Test the "to" attribute of related fields """

    def test_to_as_model_should_be_converted(self):
        class Foo(TestRedisModel):
            namespace = 'related-to-model'

        class Bar(TestRedisModel):
            namespace = 'related-to-model'
            foo = FKStringField(Foo)

        self.assertEqual(Bar._redis_attr_foo.related_to, 'related-to-model:foo')

    def test_to_as_model_name_should_be_converted(self):
        class Foo(TestRedisModel):
            namespace = 'related-to-name'

        class Bar(TestRedisModel):
            namespace = 'related-to-name'
            foo = FKStringField('Foo')

        self.assertEqual(Bar._redis_attr_foo.related_to, 'related-to-name:foo')

    def test_to_as_full_name_should_be_kept(self):
        class Foo(TestRedisModel):
            namespace = 'related-to-full'

        class Bar(TestRedisModel):
            namespace = 'related-to-full'
            foo = FKStringField('related-to-full:Foo')

        self.assertEqual(Bar._redis_attr_foo.related_to, 'related-to-full:foo')

    def test_to_as_self_should_be_converted(self):
        class Foo(TestRedisModel):
            namespace = 'related-to-self'
            myself = FKStringField('self')

        self.assertEqual(Foo._redis_attr_myself.related_to, 'related-to-self:foo')


class RelatedNameTest(LimpydBaseTest):
    """ Test the "related_name" attribute of related fields """

    def test_undefined_related_name_should_be_auto_created(self):
        core_devs = Group(name='limpyd core devs')
        ybon = Person(name='ybon')
        ybon.prefered_group.set(core_devs._pk)

        self.assertEqual(set(core_devs.person_set()), set([ybon._pk]))

    def test_defined_related_name_should_exists_as_collection(self):
        core_devs = Group(name='limpyd core devs')
        ybon = Person(name='ybon')
        core_devs.owner.hset(ybon._pk)

        self.assertEqual(set(ybon.owned_groups()), set([core_devs._pk]))
        self.assertEqual(set(ybon.owned_groups()), set(Group.collection(owner=ybon._pk)))

    def test_placeholders_in_related_name_should_be_replaced(self):
        class PersonTest(TestRedisModel):
            namespace = 'related-name'
            name = fields.PKField()
            most_hated_group = FKStringField('related-tests:Group', related_name='%(namespace)s_%(model)s_set')

        ms_php = Group(name='microsoft php')
        ybon = PersonTest(name='ybon')
        ybon.most_hated_group.set(ms_php._pk)

        self.assertTrue(hasattr(ms_php, 'related_name_persontest_set'))
        self.assertEqual(set(ms_php.related_name_persontest_set()), set([ybon._pk]))

    def test_related_name_should_follow_namespace(self):
        class SubTest():
            """
            A class to create another model with the name "Group"
            """

            class Group(TestRedisModel):
                namespace = "related-name-ns"
                name = fields.PKField()

            class PersonTest(TestRedisModel):
                namespace = "related-name-ns"
                name = fields.PKField()
                first_group = FKStringField("related-tests:Group")
                second_group = FKStringField('Group')

            @staticmethod
            def run():
                group1 = Group(name='group1')  # namespace "related-name"
                group2 = SubTest.Group(name='group2')  # namespace "related-name-ns"

                person = SubTest.PersonTest(name='person')
                person.first_group.set(group1._pk)
                person.second_group.set(group2._pk)

                self.assertEqual(set(group1.persontest_set()), set([person._pk]))
                self.assertEqual(set(group2.persontest_set()), set([person._pk]))

        SubTest.run()

    def test_related_names_should_be_unique_for_a_model(self):
        with self.assertRaises(ImplementationError):
            class Foo(TestRedisModel):
                namespace = 'related-name-uniq'
                father = FKHashableField('self')
                mother = FKHashableField('self')

        with self.assertRaises(ImplementationError):
            class Foo(TestRedisModel):
                namespace = 'related-name-uniq'
                father = FKHashableField('self', related_name='parent')
                mother = FKHashableField('self', related_name='parent')

        with self.assertRaises(ImplementationError):
            class Foo(TestRedisModel):
                namespace = 'related-name-uniq'
                father = FKHashableField('self', related_name='%(namespace)s_%(model)s_set')
                mother = FKHashableField('self', related_name='%(namespace)s_%(model)s_set')

        with self.assertRaises(ImplementationError):
            class Foo(TestRedisModel):
                namespace = 'related-name-uniq'
                father = FKHashableField('Bar')
                mother = FKHashableField('Bar')

            class Bar(TestRedisModel):
                namespace = 'related-name-uniq'

    def test_related_names_should_work_with_subclasses(self):

        class Base(TestRedisModel):
            abstract = True
            namespace = 'related-name-sub'
            name = fields.PKField()
            a_field = FKStringField('Other', related_name='%(namespace)s_%(model)s_related')

        class ChildA(Base):
            pass

        class ChildB(Base):
            pass

        class Other(TestRedisModel):
            namespace = 'related-name-sub'
            name = fields.PKField()

        other = Other(name='foo')
        childa = ChildA(name='bar', a_field=other._pk)
        childb = ChildB(name='baz', a_field=other._pk)

        self.assertTrue(hasattr(other, 'related_name_sub_childa_related'))
        self.assertTrue(hasattr(other, 'related_name_sub_childb_related'))
        self.assertEqual(set(other.related_name_sub_childa_related()), set([childa._pk]))
        self.assertEqual(set(other.related_name_sub_childb_related()), set([childb._pk]))

    def test_related_name_as_invalid_identifier_should_raise(self):
        with self.assertRaises(ImplementationError):
            class PersonTest(TestRedisModel):
                namespace = 'related-name-inv'
                group = FKStringField('related-tests:Group', related_name='list-of-persons')


class FKTest(LimpydBaseTest):

    def test_fk_can_be_given_as_object(self):
        core_devs = Group(name='limpyd core devs')
        ybon = Person(name='ybon')

        core_devs.owner.hset(ybon)
        self.assertEqual(core_devs.owner.hget(), ybon._pk)
        self.assertEqual(set(ybon.owned_groups()), set([core_devs._pk]))

    def test_can_update_fk(self):
        core_devs = Group(name='limpyd core devs')
        ybon = Person(name='ybon')
        twidi = Person(name='twidi')

        core_devs.owner.hset(ybon)
        self.assertEqual(set(ybon.owned_groups()), set([core_devs._pk]))

        core_devs.owner.hset(twidi)
        self.assertEqual(set(ybon.owned_groups()), set())
        self.assertEqual(set(twidi.owned_groups()), set([core_devs._pk]))

    def test_many_fk_can_be_set_on_same_object(self):
        core_devs = Group(name='limpyd core devs')
        fan_boys = Group(name='limpyd fan boys')
        twidi = Person(name='twidi')

        core_devs.owner.hset(twidi)
        fan_boys.owner.hset(twidi)
        self.assertEqual(set(twidi.owned_groups()), set([core_devs._pk, fan_boys._pk]))

    def test_fk_can_be_set_on_same_model(self):
        main_group = Group(name='limpyd groups')
        core_devs = Group(name='limpyd core devs')
        fan_boys = Group(name='limpyd fan boys')

        core_devs.parent.set(main_group)
        fan_boys.parent.set(main_group)
        self.assertEqual(set(main_group.children()), set([core_devs._pk, fan_boys._pk]))

    def test_deleting_an_object_must_clear_the_fk(self):
        main_group = Group(name='limpyd groups')
        core_devs = Group(name='limpyd core devs')
        fan_boys = Group(name='limpyd fan boys')
        ybon = Person(name='ybon')

        core_devs.owner.hset(ybon)
        ybon.delete()
        self.assertIsNone(core_devs.owner.hget())

        core_devs.parent.set(main_group)
        fan_boys.parent.set(main_group)
        main_group.delete()
        self.assertIsNone(core_devs.parent.get())
        self.assertIsNone(fan_boys.parent.get())

    def test_deleting_a_fk_must_clean_the_collection(self):
        core_devs = Group(name='limpyd core devs')
        ybon = Person(name='ybon')

        core_devs.owner.hset(ybon)
        core_devs.delete()
        self.assertEqual(set(ybon.owned_groups()), set())


class M2MSetTest(LimpydBaseTest):
    pass


class M2MListTest(LimpydBaseTest):

    class Group2(TestRedisModel):
        members = M2MListField(Person, related_name='members_set2')


class M2MSortedSetTest(LimpydBaseTest):

    class Group3(TestRedisModel):
        members = M2MSortedSetField(Person, related_name='members_set3')


if __name__ == '__main__':
    unittest.main()
