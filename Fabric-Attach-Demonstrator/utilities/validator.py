###########################################################################
# created by Markus Nikulski
#         markus@nikulski.net
#         created 18. Jul. 2024
#

__version__ = "1.0.0"
__author__  = "Markus Nikulski (markus@nikulski.net)"

import json
from jsonschema import Draft202012Validator, validators


def extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for property, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(property, subschema["default"])

            # type cast
            instance[property] = type_cast(instance[property], subschema)
            # type cast end

        for error in validate_properties(validator, properties, instance, schema, ):
            yield error

    def type_cast(value, subschema):
        # only type cast string values
        if isinstance(value, str):
            if subschema['type'] == 'boolean' and value in ['true', 'false']:
                return value == 'true'

            elif subschema['type'] == 'integer' and value.isdigit():
                return int(value)

        return value

    return validators.extend(
        validator_class, {"properties": set_defaults},
    )


with open('utilities/schema.json', 'r') as file:
    schema = json.load(file)

ConfigValidatorClass = extend_with_default(Draft202012Validator)
configValidator = ConfigValidatorClass(schema=schema)
