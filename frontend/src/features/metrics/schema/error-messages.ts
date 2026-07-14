/**
 * Human messages for M1/M4 validator stable codes.
 * Unmapped codes fall back to the server message.
 */
export const ERROR_CODE_MESSAGES: Record<string, string> = {
  E_SCHEMA: "Document does not match the propel/v1 schema.",
  E_OP_TYPE: "That operator is not valid for this field type.",
  E_FILTER_DEPTH: "Filters can nest at most 3 levels.",
  E_FILTER_SHAPE: "Filter shape is invalid.",
  E_UNKNOWN_FIELD: "Unknown field for this entity.",
  E_UNKNOWN_ENTITY: "Unknown entity.",
  E_FIELD_ROLE: "Field role is not allowed here.",
  E_ENUM_VALUE: "Value is not in the field's enum.",
  E_VALUE_TYPE: "Value type does not match the field.",
  E_VISIBILITY_ESCALATION: "Variants cannot broaden visibility above the parent.",
  E_CARDINALITY: "Dimension cardinality exceeds the allowed threshold.",
  E_FORMULA_SYNTAX: "Formula expression could not be parsed.",
  E_FORMULA_UNKNOWN_INPUT: "Formula references an unknown input name.",
  E_MISSING_REF: "Referenced metric was not found.",
  E_DERIVED_NESTING: "Derived metrics cannot reference other derived metrics.",
  E_ADVANCED_REQUIRED: "Raw SQL requires metadata.advanced: true.",
};

export function messageForCode(code: string, fallback: string): string {
  return ERROR_CODE_MESSAGES[code] ?? fallback;
}
