# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from django.core.files.base import File
from django.core.files.storage import default_storage
from django.db.models.fields.files import FileField as _FileField, FieldFile as _FieldFile
from django.utils.text import capfirst
from django.utils.translation import ugettext_lazy
from multifileinput.formfields import FileField as FileFormField
try:
    import json
except ImportError:
    from django.utils import simplejson as json
try:
    string_types = basestring
except NameError:
    string_types = str
try:
    callable = callable
except NameError:
    def callable(obj):
        return any("__call__" in klass.__dict__ for klass in type(obj).__mro__)


class FileItem(_FieldFile):
    
    def __init__(self, instance, field, name):
        super(FileItem, self).__init__(instance, field, name)
    
    def delete(self, save=True):
        # Only close the file if it's already open, which we know by the
        # presence of self._file
        filename = self.name
        if hasattr(self, '_file'):
            self.close()
            del self.file
        self.storage.delete(self.name)
        self.name = None
        # Delete the filesize cache
        if hasattr(self, '_size'):
            del self._size
        self._committed = False
        if save:
            files = getattr(self.instance, self.field.name)
            files.remove([filename])
            self.instance.save()
    
    def save(self, name, content, save=True):
        filename = self.field.generate_filename(self.instance, name)
        self.name = self.storage.save(filename, content)
        # Update the filesize cache
        self._size = content.size
        self._committed = True
        if save:
            self.instance.save()
        return self.name


class FieldFiles(object):
    
    def __init__(self, descriptor, instance):
        self.descriptor = descriptor
        self.instance = instance
        self.clear()
    
    def clear(self):
        self._files = []
        self._files_remove = set() # set of file.name
    
    def append(self, f):
        fieldfile = self.descriptor.conv_to_file(f, self.instance)
        self._files.append(fieldfile)
        
    def extend(self, l):
        for f in l:
            self.append(f)
    
    def remove(self, f):
        if isinstance(f, string_types):
            self._files_remove.add(f)
        elif isinstance(f, File):
            self._files_remove.add(str(f))
        else:
            self._files_remove.update([str(item) for item in f if item])
            
    def remove_all(self):
        self._files_remove.update([str(item) for item in self._files if item])
        
    def should_remove(self, f):
        if str(f) in self._files_remove:
            return f._committed
        return False
        
    def __iter__(self):
        for f in self._files:
            if str(f) not in self._files_remove:
                yield f
    
    def __str__(self):
        return ", ".join([f.field.get_filename(f.name) for f in self])
    
    



class FieldFilesDescriptor(object):
    
    def __init__(self, field):
        self.field = field
        
    def __str__(self):
        return str(getattr(self, self.field.name))

    def __get__(self, instance=None, owner=None):
        if instance is None:
            raise AttributeError(
                "The '%s' attribute can only be accessed from %s instances."
                % (self.field.name, owner.__name__))
        return instance.__dict__[self.field.name]

    def __set__(self, instance, value):
        files = instance.__dict__.get(self.field.name)
        if files is None: # initialize
            files = instance.__dict__[self.field.name] = FieldFiles(self, instance)
        if files is value:
            return
        elif not value:
            files.remove_all()
            return
        elif isinstance(value, FieldFiles):
            files.remove(value._files_remove)
            files.extend(value)
            return
        elif isinstance(value, File):
            files.remove_all()
            files.append(value)
            return
        elif isinstance(value, string_types):
            try:
                value = json.loads(value)
                if not isinstance(value, string_types):
                    files.extend(value)
                else:
                    files.append(value)
            except ValueError:
                files.append(value)
            return
        elif isinstance(value, dict):
            files.remove(value.get("delete", ()))
            value = value.get("add", ())
            files.extend(value)
            return
    
    def conv_to_file(self, obj, instance):
        field = self.field
        file_class = field.attr_class
        if isinstance(obj, string_types):
            f = file_class(instance, field, obj)
            return f
        elif isinstance(obj, file_class):
            if not hasattr(obj, 'field'):
                obj.instance = instance
                obj.field = field
                obj.storage = field.storage
            return obj
        elif isinstance(obj, File):
            file_copy = file_class(instance, field, obj.name)
            file_copy.file = obj
            file_copy._committed = False
            return file_copy
        else:
            raise ValueError("Could not convert {0} to {1}".format(obj, file_class))


class FileField(_FileField):
    # The class to wrap instance attributes in. Accessing the file object off
    # the instance will always return an instance of attr_class.
    attr_class = FileItem
    
    # The descriptor to use for accessing the attribute off of the class.
    descriptor_class = FieldFilesDescriptor
    
    description = ugettext_lazy("Files")
        
    def get_internal_type(self):
        return "TextField"

    def __init__(self, verbose_name=None, name=None, upload_to='', storage=None, **kwargs):
        #TODO: アップロード可能なファイルの総数、トータルのサイズチェック、ファイルの有無チェック、ストレージからファイルを消すか
        for arg in ('primary_key', 'unique', 'choices'):
            if arg in kwargs:
                raise TypeError("'%s' is not a valid argument for %s." % (arg, self.__class__))
        self.storage = storage or default_storage
        self.upload_to = upload_to
        if callable(upload_to):
            self.generate_filename = upload_to
        kwargs['max_length'] = kwargs.get('max_length', 100)
        super(_FileField, self).__init__(verbose_name, name, **kwargs)

    def formfield(self, **kwargs):
        """
        Returns a django.forms.Field instance for this database Field.
        """
        defaults = {'max_length': self.max_length,
                    'required': not self.blank,
                    'label': capfirst(self.verbose_name),
                    'help_text': self.help_text}
        if self.has_default():
            if callable(self.default):
                defaults['initial'] = self.default()
            else:
                defaults['initial'] = self.default
        defaults.update(kwargs)
        return FileFormField(**defaults)
    
    def save_form_data(self, instance, data):
        setattr(instance, self.name, data)
            
    def get_prep_value(self, value):
        "Returns field's value prepared for saving into a database."
        if value:
            return json.dumps([str(f) for f in value])
        else:
            return None

    def pre_save(self, model_instance, add):
        "Returns field's value just before saving."
        new_files = []
        files = getattr(model_instance, self.name)
        for f in files._files:
            if not add and files.should_remove(f):
                f.delete(save=False)
            elif f:
                new_files.append(f)
        for f in new_files:
            if f and not f._committed:
                f.save(str(f), f, save=False)
        files.clear()
        files.extend(new_files)
        return files

    def south_field_triple(self):
        "Returns a suitable description of this field for South."
        from south.modelsinspector import introspector
        field_class = "django.db.models.fields.TextField"
        args, kwargs = introspector(self)
        return (field_class, args, kwargs)


    
    
