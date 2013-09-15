# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from django.core.exceptions import ValidationError
from django.forms.fields import FileField as _FileField
from django.forms.util import flatatt
from django.forms.widgets import CheckboxInput, FileInput as _FileInput
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy
import base64
import binascii
try:
    from django.utils.encoding import force_text
except ImportError:
    from django.utils.encoding import force_unicode as force_text


class FileInput(_FileInput):

    def __init__(self, attrs=None):
        if attrs is not None:
            self.attrs = attrs.copy()
        else:
            self.attrs = {"multiple": "multiple"}

    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs, type=self.input_type, name=name)
        if final_attrs and final_attrs.get("multiple"):
            final_attrs["name"] += "[]"
        final_attrs = {key: conditional_escape(val) for key, val in final_attrs.items()}
        return mark_safe(force_text('<input{0} />'.format(flatatt(final_attrs))))
    
    def value_from_datadict(self, data, files, name):
        try: 
            f = files.getlist(name + "[]") # multiple
            return {"add": f}
        except AttributeError:
            f = files.get(name, None)
            val = f and [f] or []
            return {"add": val}


class ClearableFileInput(FileInput):
    initial_text = ugettext_lazy('Currently')
    clear_checkbox_label = ugettext_lazy('Delete')
    template_with_initial = """
                            <div id="id_{name}_div" class="file-upload">
                              <div class="current-files">
                                {current_files_html}
                              </div>
                              {file_input}
                            </div>"""
    template_with_clear = """
                            <div class="current-file">
                              {initial_text}: <a href="{file_url}" target="_blank">{file_shortname}</a> 
                              <span class="clear-checkbox">
                                  {clear_checkbox_input}
                                  <label for="{clear_checkbox_id}">
                                    {clear_checkbox_label}
                                  </label>
                              </span>
                            </div>"""

    def render(self, name, value, attrs=None):
        initial_files = []
        if value:
            template_with_clear = self.template_with_clear
            files = isinstance(value, dict) and value.get("initial") or value #TODO: FieldFilesが渡される条件を確認
            for i, f in enumerate(files or ()):
                if f and hasattr(f, "url"):
                    clear_checkbox_name = self.clear_checkbox_name(name, f)
                    clear_checkbox_id = self.clear_checkbox_id(name, i)
                    clear_checkbox_input = CheckboxInput().render(clear_checkbox_name,
                                                                  False, 
                                                                  attrs={'id': clear_checkbox_id})
                    file_url = conditional_escape(f.url)
                    file_name = conditional_escape(f.name)
                    file_shortname = conditional_escape(f.filename())
                    html = template_with_clear.format(initial_text=self.initial_text,
                                                      file_url=file_url,
                                                      file_name=file_name,
                                                      file_shortname=file_shortname,
                                                      clear_checkbox_input=clear_checkbox_input,
                                                      clear_checkbox_id=clear_checkbox_id,
                                                      clear_checkbox_label=self.clear_checkbox_label)
                    initial_files.append(html)
        file_input = super(ClearableFileInput, self).render(name, value, attrs)
        current_files_html = "".join(initial_files)
        html = self.template_with_initial.format(name=name,
                                                 current_files_html=current_files_html,
                                                 file_input=file_input
                                                 )
        return mark_safe(force_text(html))

    def value_from_datadict(self, data, files, name):
        value = super(ClearableFileInput, self).value_from_datadict(data, files, name)
        clear_files = self.clear_filename_set_from_datadict(data, name)
        value["delete"] = clear_files
        return value

    def __init__(self, attrs=None, template_with_initial=None, template_with_clear=None):
        super(ClearableFileInput, self).__init__(attrs)
        if template_with_initial is not None:
            self.template_with_initial = template_with_initial
        if template_with_clear is not None:
            self.template_with_clear = template_with_clear
    
    def get_clear_checkbox_prefix(self, name):
        return  name + "-clear-"
    
    def clear_checkbox_id(self, name, idx):
        return "{0}{1}".format(self.get_clear_checkbox_prefix(name), idx)
    
    def clear_checkbox_name(self, name, f):
        prefix = self.get_clear_checkbox_prefix(name)
        b32filename = base64.b32encode(f.name.encode("utf-8"))
        return prefix + b32filename.decode("utf-8").replace("=", "-")

    def decode_clear_checkbox_name(self, checkbox_name, name):
        prefix = self.get_clear_checkbox_prefix(name)
        s = checkbox_name[len(prefix):].replace("-", "=").encode("utf-8")
        return base64.b32decode(s).decode("utf-8")
        
    def clear_filename_set_from_datadict(self, data, name):
        prefix = self.get_clear_checkbox_prefix(name)
        clear_set = set()
        for checkbox_name, value in data.items():
            if checkbox_name.startswith(prefix) and value == 'on':
                try:
                    filename = self.decode_clear_checkbox_name(checkbox_name, name)
                    clear_set.add(filename)
                except (TypeError, binascii.Error):
                    pass
        return clear_set


class FileField(_FileField):
    widget = ClearableFileInput

    def __init__(self, *args, **kwargs):
        super(FileField, self).__init__(*args, **kwargs)
        if not hasattr(self, "allow_empty_file"):
            self.allow_empty_file = kwargs.pop('allow_empty_file', False) # django1.4?
    
    def bound_data(self, data, initial):
        data["initial"] = initial
        return data

    def clean(self, data, initial=None):
        #TODO: アップロード可能なファイルの総数、トータルのサイズチェック、ファイルの有無チェック
        
#         # If the widget got contradictory inputs, we raise a validation error
#         if data is FILE_INPUT_CONTRADICTION:
#             raise ValidationError(self.error_messages['contradiction'])
        # False means the field value should be cleared; further validation is
        # not needed.
        if data is False:
            if not self.required:
                return False
            # If the field is required, clearing is not possible (the widget
            # shouldn't return False data in that case anyway). False is not
            # in validators.EMPTY_VALUES; if a False value makes it this far
            # it should be validated from here on out as None (so it will be
            # caught by the required check).
            data = None
        if not data and initial:
            return initial
        ###return super(FileField, self).clean(data)###
        """
        Validates the given value and returns its "cleaned" value as an
        appropriate Python object.

        Raises ValidationError for any errors.
        """
        value = data
        value = self.to_python(value)
        self.validate(value)
        self.run_validators(value)
        return value

    def to_python(self, data):
        if not data:
            return None
        # UploadedFile objects should have name and size attributes.
        for f in data.get("add", ()):
            try:
                file_name = f.name
                file_size = f.size
            except AttributeError:
            # TODO: どのファイルにエラーが含まれていたか分かるようにエラーメッセージを変える
            # TODO: for文でエラーが大量にでないようにする
                raise ValidationError(self.error_messages['invalid'])
            if self.max_length is not None and len(file_name) > self.max_length:
                error_values = {'max': self.max_length, 'length': len(file_name)}
                raise ValidationError(self.error_messages['max_length'] % error_values)
            if not file_name:
                raise ValidationError(self.error_messages['invalid'])
            if not self.allow_empty_file and not file_size:
                raise ValidationError(self.error_messages['empty'])
        return data 
    
    
    
