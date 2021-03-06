# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Datatable.py
# Author  : Arif Dzikrullah
# E-Mail  : ardzix@hotmail.com
#
# Please write your identity if you change this file
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++

from django.db.models import Q
import types
import datetime
import arrow
from django.conf import settings
from json_response import JSONResponse
import sys
import copy
# reload(sys)
# sys.setdefaultencoding('utf-8')

# =============================================
# The Datatable
# this class serve datatable client request
# so the client can request data, sort, search and paginate
#
# i know this file is a mess, i hope you can improve this
# =============================================


class Datatable(object):

    # Initialize class attribute
    request = None
    obj = None
    key = ""
    deff_button = True
    time_format = "MMM. D, YYYY h:mm a"
    offset = 0
    limit = 10
    data = {}
    ordering = ""
    posts = None
    error = False
    error_messages = None
    defer = []
    lookup_defer = []
    lookup_m2m_defer = []
    search_defer = []
    search_uid_defer = []
    looked_up_defer_index = []
    looked_up_m2m_defer_index = []
    search_query = []
    method_origin_field = []
    method_field = []
    custom_button = []

    def __init__(self, request, obj, defer, key="id62", deff_button=True, custom_button=[], *args, **kwargs):
        '''
        When you instantiate a variable with this class, you need to provide:
        - request   : the request needed to get url parameter sent by client
        - obj       : this is model object
        - defer     : list of column that need to be returned
        - key       : column name for table id
        - deff_button : if true, button edit and delete will be shown on last column automatically
        - custom_button : custom button that will be rendered after default button
        '''

        self.request = request
        self.obj = obj
        self.defer = defer
        self.key = key
        self.deff_button = deff_button
        self.custom_button = custom_button
        self.offset = int(request.GET.get("start", 0))
        self.limit = int(request.GET.get("length", 10)) + self.offset

        # handle filter date
        self.filter_date_key = kwargs.get("date_filter_key", 'created_at')
        self.start_date = kwargs.get('start_date', None)
        self.start_filter = '%s__gte' % self.filter_date_key

        self.end_date = kwargs.get('end_date', None)
        self.end_filter = '%s__lte' % self.filter_date_key

        self.obj = self.filter_date_range()

    """ 
    filter by views with add kwargs start_date or/and end_date
    date type is string and use "YYYY-MM-DD" format
    example:
    d = Datatable(
        request, qs, defer, custom_button=custom_buttons,
        date_filter_key='start_date', start_date="2020-01-01", end_date='2020-03-28')
    """
    def filter_date_range(self):
        key = self.filter_date_key
        start_date = self.start_date
        end_date = self.end_date
        obj = self.obj

        start_filter = '%s__gte' % key
        end_filter = '%s__lte' % key

        if start_date:
            obj = obj.filter(**{ start_filter: start_date })
        
        if end_date:
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            end_date = end_date + datetime.timedelta(seconds=86400)
            obj = obj.filter(**{ end_filter: end_date })
            
        return obj

    def perform_query(self):
        request = self.request
        obj = self.obj

        '''
        able filter date by query string, but default filter coulumn is 'created_at'
        url?start_date=2020-01-01&end_date=2020-12-12
        '''
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)

        if not self.start_date and start_date:
            obj = obj.filter(**{ self.start_filter: start_date })
        
        if not self.end_date and end_date:
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
            end_date = end_date + datetime.timedelta(seconds=86400)
            obj = obj.filter(**{ self.end_filter: end_date })

        # Get ordering parameter
        if not request.GET.get("order[0][dir]", "") == "asc":
            self.ordering = "-"

        # Get search/filter value
        search_query = request.GET.get('search[value]', '')

        # If search/filter value not provided
        if search_query == '':
            # We don't perform search
            self.posts = obj
            self.data['recordsFiltered'] = obj.count()
        else:
            # else, we perform search
            search = self.search(search_query=search_query)
            # If search returned none
            if search != None:
                # Than it was error, so we need to perform search error
                self.search_error(error_messages=search)

        # Then we perform ordering
        self.order()

        # Put some data parameter
        self.data['draw'] = request.GET.get('draw')
        self.data['recordsTotal'] = obj.count()

        # Perform append
        self.append()

    # get data is called when you need data in this instance
    def get_data(self):
        self.perform_query()
        # if there is an error in this instance
        if self.error:
            # then we return the error message
            return self.error_messages

        # Finally we return the data on this instace
        return JSONResponse(self.data)

    def set_method_defer(self, method=[]):
        '''
        If you have a method that modify field data, you can call
        this set_method_defer and this will return the value from
        method you specified

        example : 
        d.set_method_defer([{'origin':'field', 'method': 'method'}])
         - origin: origin field in model
         - method: method that you want get
        '''
        for m in method:
            self.method_origin_field.append(m['origin'])
            self.method_field.append(m['method'])

    def set_lookup_m2m_defer(self, lookup=[]):
        '''
        Use this method if you want your column value to be looked up to another m2m models
        look up field is a relational field
        '''
        lookup_dict_list = []
        looked_up_defer_index = []
        defer = copy.copy(self.defer)
        for k, l in enumerate(lookup):
            l_dict = {"lookup_field": l}
            splited_l = l.split("__")
            field = ""
            if len(splited_l) > 0:
                l_dict['field'] = splited_l[0]
                l_dict['index'] = defer.index(l_dict['field'])
                defer[l_dict['index']] = '-'
                if len(self.obj) > 0:
                    l_dict['model'] = self.obj[0].__class__
                    looked_up_defer_index.append(l_dict['index'])
                    lookup_dict_list.append(l_dict)

        self.looked_up_m2m_defer_index = looked_up_defer_index
        self.lookup_m2m_defer = lookup_dict_list

    def set_lookup_defer(self, lookup=[]):
        '''
        Use this method if you want your column value to be looked up to another models
        look up field is a relational field
        '''
        lookup_dict_list = []
        looked_up_defer_index = []
        defer = copy.copy(self.defer)
        for k, l in enumerate(lookup):
            l_dict = {"lookup_field": l}
            splited_l = l.split("__")
            field = ""
            if len(splited_l) > 0:
                l_dict['field'] = splited_l[0]
                l_dict['index'] = defer.index(l_dict['field'])
                defer[l_dict['index']] = '-'
                if len(self.obj) > 0:
                    l_dict['model'] = self.obj[0].__class__
                    looked_up_defer_index.append(l_dict['index'])
                    lookup_dict_list.append(l_dict)

        self.looked_up_defer_index = looked_up_defer_index
        self.lookup_defer = lookup_dict_list

    # Set error status true and give error message if there is no search result
    def search_error(self, error_messages):
        self.error = True
        self.error_messages = error_messages

    def search(self, search_query):
        self.search_query = search_query

        # we check, is it searchable or not? searchable parameter sent by client in request url
        # if it is searchable and not in lookup defer, we append it to search_defer
        search_defer = []
        u_id = []
        ld_index = 0
        for n in range(len(self.defer)):
            if self.request.GET.get('columns['+str(n)+'][searchable]', 'false') == 'true':
                if len(self.lookup_defer) > 0:
                    cleaned_lookup_defer = []
                    for ld in self.lookup_defer:
                        if type(ld).__name__ == "dict":
                            cleaned_lookup_defer.append(ld['field'])
                        else:
                            cleaned_lookup_defer.append(ld)
                    if self.defer[n] not in cleaned_lookup_defer:
                        search_defer.append(self.defer[n]+"__icontains")
                    else:
                        keyword = self.lookup_defer[ld_index]['lookup_field'] + \
                            "__icontains"
                        kwargs = {
                            keyword: self.search_query
                        }
                        u_id += list(self.lookup_defer[ld_index]['model'].objects.filter(
                            **kwargs).values_list(self.key, flat=True))
                        ld_index += 1

                else:
                    search_defer.append(self.defer[n]+"__icontains")

        self.search_defer = search_defer
        self.search_uid_defer = u_id
        self.perform_search()

    # We make filter query from search value in this method
    def perform_search(self):

        # We make filter queries from the defer
        queries = [Q(**{f: self.search_query}) for f in self.search_defer]
        queries.append(Q(**{"%s__in" % self.key: self.search_uid_defer}))
        # We instantiate a variable called QS from Q class
        qs = Q()
        # for every query in filter queries
        for query in queries:
            # we make or query for every search defer with same value
            qs = qs | query

        # Then we try to
        try:
            # append the filter methode to the queryset object with qs object as parameter
            self.posts = self.obj.filter(qs)
            # also the record filtered rows count need to passed to the return
            self.data['recordsFiltered'] = self.obj.filter(qs).count()
        # if we failed to try
        except Exception as e:
            # we sent an error response to client
            return JSONResponse({'error': 'error in search parameter', 'error detail': str(e), 'suggestion': 'Only enable varchar data type only for search'})

    # we add ordering method to queryset object with ordering parameter sent by client
    def order(self):
        self.posts = self.posts.order_by(
            self.ordering+self.defer[int(self.request.GET.get('order[0][column]', 0))])

    # this method appending every field from result of post object to datatable row list
    def append(self):
        self.data['data'] = []
        n = 0
        # for every post result in page requested by client, we do:
        if self.limit > -1:
            self.posts = self.posts[self.offset:self.limit]
        for v in self.posts:
            d_list = []
            # loop for every defer then
            for k, x in enumerate(self.defer):
                # get attribute of post result with defer as a key
                if k in self.looked_up_defer_index:
                    di = self.looked_up_defer_index.index(k)
                    ld = self.lookup_defer[di]
                    lf = ld['lookup_field'].split("__")
                    o = v
                    for field in lf:
                        if not o:
                            continue
                        attr = getattr(o, field)
                        o = attr

                # get attribute of post result with m2m defer as a key
                elif k in self.looked_up_m2m_defer_index:
                    di = self.looked_up_m2m_defer_index.index(k)
                    ld = self.lookup_m2m_defer[di]
                    lf = ld['lookup_field'].split("__")
                    o = v
                    attr = ", ".join(list(getattr(o, lf[0]).values_list(lf[1], flat=True)))

                # if defer in method_field, get method field value instead
                elif x in self.method_origin_field:
                    index = self.method_origin_field.index(x)
                    attr = getattr(v, self.method_field[index])
                else:
                    attr = getattr(v, x)

                # if the attribute is a method
                if type(attr) == types.MethodType:
                    # we convert the attribute velue then append it to result row
                    d_list.append(str(attr()))
                # if the attribute is datetime
                elif str(type(attr)) == "<type 'datetime.datetime'>" or str(type(attr)) == "<class 'datetime.datetime'>":
                    # we convert its value (datetime) to local timezone and append it
                    locale_time = arrow.get(attr).to(settings.TIME_ZONE)
                    d_list.append(locale_time.format(self.time_format))
                # else
                else:
                    # we convert its attribute directly to a string and append it
                    d_list.append(str(attr))

            button = ""

            # if deff button is True
            if self.deff_button:
                # we add the rendered deffault button
                button = button + \
                    '<button \
                        type="button" \
                        style="margin:2px" \
                        class="\
                            btn \
                            btn-sm \
                            btn-inline \
                            btn-primary \
                            datatable-edit-button" \
                        data-toggle="tooltip" \
                        title="Cick to edit, Double click to open in new tab" \
                        data-id="%s" \
                        <span><i class="fa fa-edit"></i></span>\
                    </button>\
                    <button \
                        type="button" \
                        style="margin:2px" \
                        class="\
                            btn \
                            btn-sm \
                            btn-inline \
                            btn-danger \
                            datatable-delete-button" \
                        data-toggle="tooltip" \
                        title="Cick to delete this data" \
                        data-id="%s" \
                        <span><i class="fa fa-trash"></i></span>\
                    </button>' % (
                        str(getattr(v, self.key)),
                        str(getattr(v, self.key)),
                    )

            # for every custom button provided in parameter:
            for b in self.custom_button:
                # we render the button html
                button = button+'<button type="button" style="'+b['style']+'" class="'+b['class']+'" data-id="'+str(
                    getattr(v, self.key))+'"><span><i class="fa '+b['icon']+'"></i>&nbsp;'+b['text']+'</span></button>'
            # Then we append the rendered button to the field
            d_list.append(button)
            self.data['data'].append(tuple(d_list))
            n = n+1
