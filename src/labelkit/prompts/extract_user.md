Fill the JSON fields with text copied from the OCR text below.

- legal_name: the product name, usually the largest text or the first line.
- ingredients: the ingredient list, without the word "ingredients".
- allergens: only sentences on the label that talk about allergens. Otherwise null.
- net_quantity: the net weight or volume ("Poids net", "Peso líquido", "Net wt").
- storage: how to store the product (temperature, "keep frozen", "after opening...").
- usage: preparation or cooking instructions.
- responsible_operator: company name and address printed on the label.
- country_of_origin: only if the label states where the product comes from.
- nutrition: only if the label has a nutrition table. Copy each number into the field
  whose name is printed next to it, and set `basis` ("100g", "100ml" or "portion").
  If a number has no nutrient name next to it, leave that nutrient null.
- Every field that is not on the label must be null.

OCR text (several photos of the same product, separated by ---):
"""
{ocr_text}
"""
