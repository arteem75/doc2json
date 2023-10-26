import os
import re
import urllib
import json

from bs4 import BeautifulSoup

from docparser.base import APIDocConverter
from docparser.utils import file2html, dict2json



class SwiftAPIDocConverter(APIDocConverter):
    EXCLUDED_FILES = []
    PROTECTED = ""
    PUBLIC = ""

    def __init__(self, args):
        super().__init__()
        self.class_name = None
    def process(self, args):
        for base in os.listdir(args.input):
            if base in self.EXCLUDED_FILES:
                continue
            apidoc_path = os.path.join(args.input, base)
            if not apidoc_path.endswith(".html"):
                continue
            data = self.process_class(file2html(apidoc_path))
            if data:
                data["language"] = args.language
            dict2json(args.output, data)

    def process_class(self,html_content):
        self.class_name = self.extract_name(html_content)
        extracted_elements = self.preprocess_html(html_content)
        out_func = []
        out_var = []
        out_init = []
        out_typealias = []
        for elem,cond in extracted_elements:
                if elem.startswith('func ') or elem.startswith('static func') or elem.startswith('subscript'):
                    out_func.append((self.process_methods(elem),cond))

                if elem.startswith('var' ) or elem.startswith('static var '):
                    out_var.append((self.process_fields(elem),cond))

                if elem.startswith('init'):
                    out_init.append((self.process_methods(elem),cond))

                if elem.startswith('typealias'):
                    out_typealias.append((self.format_typealias(elem),cond))
                    
            #  preprocess protocols i.e. find out which are conditional (the struct/class element needs to conform to some protocol) 
            #  also extract parent classes
        [protocols_cond,protocols],parents = self.extract_inheritance(html_content)
        func_json = self.jsonify_func(out_func)
        var_json = self.jsonify_var(out_var)
        init_json = self.jsonify_func(out_init)
        typealias_json = self.jsonify_typealiases(out_typealias)        
        protocol_json = self.jsonify_protocols(protocols_cond,protocols)
        name_json = self.class_name
        merged_json = {
            
            "methods":[],
            "fields":[],
            "implements":[],
            "typealiases":[],
            "inherits":[],
            "language":"swift"
        }
        merged_json["methods"]= func_json
        merged_json["fields"] = var_json
        merged_json["implements"] = protocol_json
        merged_json["inherits"] = parents
        merged_json["methods"] += init_json
        merged_json["typealiases"] = typealias_json

        merged_json = {**name_json, **merged_json}
        return merged_json










    def jsonify_func(self,data):
        json_data = []
        for entry,cond in data:
            entry_dict = {
            "name": entry[0],
            "type parameters": entry[1],
            "parameters": ", ".join(entry[2]),
            "throws": entry[3],
            "return_type": entry[4],
            "conditional": str(cond),
            "static": entry[5],
            "is_constructor":entry[6],
            "access_mod":entry[7]
        }
            json_data.append(entry_dict)
        return json_data


    def jsonify_var(self,data):
        json_data = []
        for entry,cond in data:        
            
            entry_dict = {
            "name": entry[0],
            "return_type": entry[1],
            "conditional": cond,
            "static": entry[2],
            "access_mod":entry[3]
        }
            json_data.append(entry_dict)
        return json_data
    def jsonify_protocols(self,pr_cond,pr_no_cond):
        json_data =[]


        for entry in pr_no_cond:
            entry_dict = {
                "name": str(entry),
                "conditional": "false"
            }
            json_data.append(entry_dict)
        for entry in pr_cond:
            entry_dict = {
                "name": str(entry),
                "conditional": "true"
            }
            json_data.append(entry_dict)
        return json_data

    def jsonify_typealiases(self,ta):
        json_data = []
        for entry,cond in ta:
            entry_dict = {
                "name": str(entry),
                "conditional": str(cond)
            }
            json_data.append(entry_dict)
        return json_data


        
        


    def erase_unmatched_parenthesis(self,s: str) -> str:

        if s.count("(") < s.count(")"):
            last_index = s.rfind(")")
            s = s[:last_index] + s[last_index+1:]
        return s
    def format_typealias(self,ta_signature):
        ta_pattern = r'typealias\s+(\w+)'
        match = re.search(ta_pattern,ta_signature)
        if match:
            ta_name = match.group(1)
            #print(ta_name)
        return ta_name

    def process_fields(self,var_signature):
        #var_pattern = r'var\s+(\w+):\s+([\w\.\?\[\]\s\:<>\-]+)'
        var_pattern = r'var\s+(\w+):\s+([\w\.\?\[\]\s\:<>\-,]+)'
        match = re.search(var_pattern, var_signature)
        if match:
            var_name = match.group(1)
            var_type = match.group(2).strip()
            is_static = "false"
            access_mod = "public"  #TODO need revision
            if 'static var ' in var_signature:
                is_static = "true"
            return [var_name, var_type, is_static,access_mod]
        else: 
            return [None, None,None,None]


        return

    def process_methods(self,func_signature):
        
        #func_name_pattern = r'func (\w+)'
        #return_type_pattern = r'->\s+(\w+)'
        #return_type_pattern = r'->\s+([\w\.\?\[\]\s]+)(?![\s\S]*->)'
        #return_type_pattern= r'->\s+([\w\.\?\[\]\s\:<>\-]+)(?![\s\S]*->)'
        #parameters_pattern = r'\(([^)]+\))'  
        #func_name_pattern = r'func (\w+|\+=|\+|\==|\~=|\!=|\|\||&&|-=|!)'
        func_name_pattern = r'func\s+((\w+)|([=\-\+!*%<>&|^~/.?]+))'
        #type_parameters_pattern = r'<(.+?)>'
        type_parameters_pattern = r'<((?:(?!<).)+)>\('
        

        return_type_pattern= r'->\s*([\w\.\?\[\],\s\:<>\-]+)(?![\s\S]*->)'
        parameters_pattern = r'\(((?:[^()]|\((?:[^()]|\([^()]*\))*\))*)\)'

        throws_pattern = r'(rethrows|throws)'

    # Extract details using regex
        type_parameters = re.search(type_parameters_pattern, func_signature)
        parameters = re.findall(parameters_pattern, func_signature)
        throws = re.search(throws_pattern, func_signature)
        

        func_name = 'subscript' if func_signature.startswith('subscript') else re.search(func_name_pattern, func_signature)
        if func_name != 'subscript':
            func_name = func_name.group(1) if func_name else None
        type_parameters = type_parameters.group(1) if type_parameters else None
        throws = "true" if throws else "false"
        return_type = None
        if "->" in func_signature.split(")")[-1]:
            return_type_match = re.search(return_type_pattern, func_signature)
            return_type = return_type_match.group(1).strip() if return_type_match else None
        is_static = "false"
        is_constructor = "false"
        if 'static func ' in func_signature:
            is_static = "true"
        
        if func_name is None:
            
            if func_signature.startswith('init?'):
                func_name = 'init?'
                is_constructor = "true"
            elif func_signature.startswith('init'):
                func_name = 'init'
                is_constructor = "true"
            else:
                print('could not process' + str(func_signature))
        #print(func_name)
        access_mod = "public"  #TODO need revision
        return [func_name,type_parameters, parameters, throws, return_type,is_static,is_constructor,access_mod]

        # extracts classes that the processed class inherits from and the protocols that the processed element conforms to
    def extract_inheritance(self,html_content):
        soup = html_content

        elements_with_constraints = []
        elements_without_constraints = []
        is_class = soup.find(id='inherits-from', class_='contenttable-title')
        inherits_from_div = soup.find('h3', id='inherits-from').find_parent('div', class_='contenttable-section') if soup.find('h3', id='inherits-from') else None
        conforms_from_div = soup.find('h3', id='conforms-to').find_parent('div', class_='contenttable-section') if soup.find('h3', id='conforms-to') else None
        

        elements_with_constraints = []
        elements_without_constraints = []
        parent_classes = []
        conforms = conforms_from_div.find_all('li',class_='relationships-item') if conforms_from_div else None
        inherits = inherits_from_div.find_all('li',class_='relationships-item') if inherits_from_div else None
        if conforms:
            for item in conforms:
                protocol_name = item.find("a").find("code").get_text()
                if item.find("div", class_="conditional-constraints"):
                    elements_with_constraints.append(protocol_name)
                else:
                    elements_without_constraints.append(protocol_name)
        if inherits:
            for item in inherits:
                class_name = item.find("a").find("code").get_text()
                parent_classes.append(class_name)
            
            
        return [elements_with_constraints,elements_without_constraints],parent_classes
        


    def extract_name(self,html_content):
        result = []
        soup:BeautifulSoup = html_content #BeautifulSoup(html_content, 'html.parser')

        attribute = soup.find(class_='token-attribute')
        keyword = soup.find(class_='token-keyword')
        identifier = soup.find(class_='token-identifier')
        generic_parameters = soup.findAll(class_='token-genericParameter')
        type_identifiers = soup.find_all(class_='type-identifier-link')
        gen_par = []
        for ti in type_identifiers:
            # Check if the previous sibling contains '&lt;' and the next sibling contains '&gt;'
            if ti.previous_sibling and '<' in ti.previous_sibling and ti.next_sibling and '>' in ti.next_sibling:
                gen_par.append(ti.get_text())

        
        for p in generic_parameters:
            p = p.get_text() if p else None
            gen_par.append(p)
        attribute = attribute.get_text() if attribute else None
        keyword = keyword.get_text() if keyword else None
        identifier = identifier.get_text() if identifier else None
        
        regex = re.compile(r'<[^>]+>') #discard html boilerplate
        clean_text = []
        for elem in result:
            clean_text.append( re.sub(regex,'',str(elem)))
        is_frozen = "true" if attribute and 'frozen' in attribute else "false"
        

        result = {
            "frozen": is_frozen,
            "data_type": str(keyword),
            "name": str(identifier),
            "type_parameters": str(gen_par)

        }

        return result

    def preprocess_html(self,html_content):

            soup = html_content

            #remove the 'see also' section
            see_also_element = soup.find(string=re.compile("See Also")) #hardcoded
            if see_also_element:
                parent_tag = see_also_element.find_parent()

                for sibling in parent_tag.find_all_next():
                    sibling.decompose()

                parent_tag.decompose()
        
            # find all elements having class 'link-block topic' that are methods/fields etc. with description, 
            # use 'link-block topic has-inline-element' for elements without description

            code_elements = soup.findAll('div', class_=["link-block topic", "link-block topic has-inline-element"])
            results = []

            #  iterate through all elements and note if they are deprecated (i.e. will be ignored)
            #  or if the method/field only exists if the struct/class conforms to stated protocol
            for code in code_elements:
                code_text = code.find('code', class_="decorated-title")
                deprecated = code.find(class_="badge badge-deprecated")
                if deprecated is not None:
                    continue
                conditional_content = code.find('div', class_="conditional-constraints content")

                code_text = code_text.get_text() if code_text else None
                if code_text is None:
                    continue

                if  conditional_content is None:
                    results.append((code_text,"false"))
                else:
                    results.append((code_text,"true"))

            return results
            


"""
    if __name__ == "__main__":
        path = '/Users/artemancikov/Desktop/bt_pup/String Apple Developer Documentation.html' 
        #path = '/Users/artemancikov/Desktop/bt_pup/Array Apple Developer Documentation.html'
        path = '/Users/artemancikov/Desktop/bt_pup/Double Apple Developer Documentation.html'
        #path = '/Users/artemancikov/Desktop/bt_pup/Dictionary Apple Developer Documentation.html'
        path = '/Users/artemancikov/Desktop/bt_pup/Bool Apple Developer Documentation.html'
        path = '/Users/artemancikov/Desktop/bt_pup/NSMutableArray Apple Developer Documentation.html'
        #path = '/Users/artemancikov/Desktop/bt_pup/NSDictionary Apple Developer Documentation.html'
        with open(path, 'r', encoding='utf-8') as file:
            
            html_content = file.read()

            #preprocess raw html by extracting <code> sections that have specified properties
            extracted_elements = preprocess_html(html_content)
            out_func = []
            out_var = []
            out_init = []
            out_typealias = []
            for elem,cond in extracted_elements:
                if elem.startswith('func ') or elem.startswith('static func '):
                    out_func.append((process_methods(elem),cond))

                if elem.startswith('var' ) or elem.startswith('static var '):
                    out_var.append((process_fields(elem),cond))

                if elem.startswith('init'):
                    out_init.append((process_methods(elem),cond))

                if elem.startswith('typealias'):
                    out_typealias.append((format_typealias(elem),cond))
                    
            #  preprocess protocols i.e. find out which are conditional (the struct/class element needs to conform to some protocol) 
            #  also extract parent classes
            [protocols_cond,protocols],parents = extract_inheritance(html_content)

            func_json = jsonify_func(out_func)
            var_json = jsonify_var(out_var)
            init_json = jsonify_func(out_init)
            typealias_json = jsonify_typealiases(out_typealias)        
            protocol_json = jsonify_protocols(protocols_cond,protocols)
            name_json = extract_name(html_content)
            merged_json = {
                
                "methods":[],
                "fields":[],
                "conforms_to":[],
                "typealiases":[],
                "inherits":[],
                "language":"swift"
            }
            merged_json["methods"].append(func_json)
            merged_json["fields"].append(var_json)
            merged_json["conforms_to"].append(protocol_json)
            merged_json["inherits"].append(parents)
            merged_json["methods"].append(init_json)
            merged_json["typealiases"].append(typealias_json)

            merged_json = {**name_json, **merged_json}

        with open('NSMutableArray.json', 'w') as merged_file:
            json.dump(merged_json, merged_file, indent=4)
        
"""
"""
    ask about SIMD's in string
    parse subscripts

    look into associated types
    look into protocols
    in java a type is derived from every class and interface


    -----tasks
    look into associated types
    look into protocols
    API graph builder for swift, look at source code of thalia
    



    ----getting familiar with Thalia, starting implementing the translator;

"""