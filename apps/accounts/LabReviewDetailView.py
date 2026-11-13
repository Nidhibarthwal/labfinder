There is a Database Table named LabCategory which is for Lab category ex: Pathology, Agriculture, Software Lab etc
Its relation will be with Branch Model.
According to Lab category there can be different fields for lab details like 
for path lab there will be home collection charges and home Collection timings
but this will not be for Software lab. there can be multiple fields like this.
in some labs it will be onsite testing, calibration charges
give a proper solution how to manage this
lab categories ex: 
Pharma lab
produuct testing lab
calibration lab
software testing

some form fields will very that we are taking in lab review time

there will be configuration on lab cateogry basis
means on lab category basis different fields for lab.
Where we are taking lab url from lab, ask lab category on that time.
crawler will run accordingly


in review-details.html in first section where we are taking address, provide a field named lab category where lab will select its category from dropdown (entries From Labcategory table).

case 1 - if lab_category in branch model is empty and user selects category, save that category to Branch model.
Fetch Dynamic schema data (table field) from labcategory table for that category and save in Category data of Branch model.
then render those fields in  review-details.html 

case 2 - if lab_category in branch model already exists and User going to change this by dropdown - Provide alert to user that "your data of category wise fields will be lost by changing category (provide in professional manner)"
if he clicks yes then Fetch Dynamic schema from labcategory table for that updated category and save in Category data of Branch model.
then render those new category's fields in  review-details.html.

lab user can update entry in those fields. dynamically update data for those fields in category_data (json) of Branch model (dynamically as already working in review-detail page by on change).
