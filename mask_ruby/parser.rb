require 'pg_query'
require 'json'
require 'etcdv3'
require 'awesome_print'
require 'hashie'

class PgQueryOpt
  @sql               = nil
  @query_parser      = nil
  @table_list        = []
  @remove_ref        = 0
  @etcd              = nil
  @etcd_host         = 'localhost'
  @etcd_port         = '2379'
  @etcd_user         = nil
  @etcd_passwd       = nil
  @pass_tag          = ''
  @tag_regex         = ''
  @data_in_etcd      = {}
  @col_list          = {}
  @ref               = nil
  @groups            = {}
  @return_column_ref = {}
  @in_function       = 0
  @name              = nil
  @mask              = true
  @change_name       = nil
  @mode              = 'select'

  def properties(sql, username, db, etcd_host, etcd_port, etcd_user, etcd_passwd, user_regex, tag_regex, default_scheme, tag_users)

    @sql            = sql
    @username       = username
    @db             = db
    @etcd_host      = etcd_host
    @etcd_port      = etcd_port
    @etcd_user      = etcd_user
    @etcd_passwd    = etcd_passwd
    @user_regex     = user_regex
    @tag_regex      = tag_regex
    @data_in_etcd   = {}
    @default_scheme = default_scheme
    @in_function    = 0
    @name           = nil
    @mask           = true
    @change_name    = nil
    @mode           = 'select'


    tag_users = tag_users.delete(' ').split(',')
    if tag_users.include?(username)
      @pass_tag = /#{@tag_regex}/.match(@sql)
      return @sql if @pass_tag
    end

    conn_etcd

    @query_parser = PgQuery.parse(@sql)
    @sql          = @sql.strip

    @tag_sql = %r{(?<=^/\*)([^\*]*)(?=\*/)}.match(@sql)
    @tag_sql = @tag_sql ? '/* ' + @tag_sql[1].strip + ' */' : ''

    if @user_id.nil?
      @user_id = /#{@user_regex}/.match(@sql)

      @user_id = @user_id[1].strip if @user_id
    end

    user_to_group

    return @sql if @groups.empty?

    i = 0
    @query_parser.tree.each do |parse_item|
      @query_parser.tree[i] = parse(parse_item)
      i                     += 1
    end
    @tag_sql + @query_parser.deparse
  rescue StandardError => e
    puts e
    puts e.backtrace.to_s
    @sql

  end

  def get_role(sql)
    parser = if @sql
               @query_parser
             else
               PgQuery.parse(sql)
             end
    tree   = parser.tree
    tree.extend Hashie::Extensions::DeepFind
    keys  = tree.deep_find_all('FuncCall')
    keys2 = tree.deep_find_all('TransactionStmt')
    keys3 = tree.deep_find_all('SelectStmt')


    if keys.nil? && keys2.nil? && !keys3.nil?
      'read'
    else
      'master'
    end
  end

  def conn_etcd
    return unless @etcd.nil?

    @etcd = if @etcd_user.empty?
              Etcdv3.new(endpoints: 'http://' + @etcd_host + ':' + @etcd_port, command_timeout: 5)
            else
              Etcdv3.new(endpoints: 'http://' + @etcd_host + ':' + @etcd_port, command_timeout: 5, user: @etcd_user, password: @etcd_passwd)
            end
  end

  def user_to_group
    data        = []
    @groups     = {}
    key_replace = []

    unless @username.nil?
      filter = '/dbuser/' + @username.strip
      key_replace.push(filter)
      data += @etcd.get(filter, range_end: filter + '0').kvs
    end

    unless @user_id.nil?
      filter = '/users/' + @user_id.strip
      key_replace.push(filter)
      data += @etcd.get(filter, range_end: filter + '0').kvs
    end

    filter = '/users/*'
    key_replace.push(filter)
    data += @etcd.get(filter, range_end: filter + '0').kvs

    filter = '/dbuser/*'
    key_replace.push(filter)
    data += @etcd.get(filter, range_end: filter + '0').kvs


    i = 0
    data.each do |val|
      val_obj = JSON.parse(val.value)
      if val_obj['enabled'].to_s == 'false'
        data.delete_at(i)
      else
        key = val.key.dup
        key_replace.each { |key_data| key.gsub! key_data, '' }
        @groups[key] = {}
      end
      i += 1
    end

    data
  end

  def etcd_data(filter_id)
    if @data_in_etcd[filter_id].nil?
      data                     = @etcd.get(filter_id, range_end: filter_id + '0')
      @data_in_etcd[filter_id] = data
    end
    return {} if @data_in_etcd[filter_id].kvs.count.zero?

    JSON.parse(@data_in_etcd[filter_id].kvs.first.value)

  end

  def get_string(node)
    return node if node.is_a?(String)
    return node['String']['str'] unless node['String'].nil?
    return nil unless node['A_Star'].nil?

    node.to_s
  end

  def get_alias(node)
    if node.is_a?(Array)
      alias_array = []
      node.each do |col|
        alias_array.push(get_string(col))
      end
      alias_array.join('.')
    else
      get_string(node)
    end
  end

  def get_col_with_table(schema, table)
    etcd_data('/' + @db + '/' + schema + '/' + table)
  end

  # @param [Object] ref
  # @param [Object] table_list
  # @return [Hash{null->null}]
  def mask(ref, table_list)
    return_column_ref = {}
    if ref.count == 1
      table_list.each do |alias_name, table|
        next unless table['columns'].find { |col| !col.key(get_string(ref[-1])).nil? }

        ref = alias_name.split('.') + [get_string(ref[-1])]
        break
      end
    end

    tab = table_list[get_alias(ref.first(ref.count - 1))] unless table_list.empty?
    unless tab.nil?
      filter = '/rules/' + @db + '/' + tab['schema'] + '/' + tab['table']
      data   = {}
      @groups.each do |key, value|
        group = etcd_data(key)
        next if group['enabled'].to_s == 'false'

        data_temp = etcd_data(filter + '/' + get_string(ref[-1]) + key)
        next if data_temp['enabled'].to_s == 'false'

        if data_temp.empty?
          data = {}
        else
          data = data_temp
          break
        end
      end

      unless data.empty?
        name = if @name.nil?
                 get_string(ref[-1])
               elsif @name.is_a?(String)
                 @name
               end

        if data['rule'] == 'send_null'
          return_column_ref = { 'ResTarget' => { 'name' => name, 'val' => { 'A_Const' => { 'val' => { 'Null' => {} } } } } }
        elsif data['rule'] == 'delete_col'
          return_column_ref = { 'del' => 1 }
        else
          change_colname = JSON.parse(data['prop'].gsub('%col%', { 'ColumnRef' => { 'fields' => ref } }.to_json))
          # TODO: Schema is not dynamic
          func = { 'funcname' => [{ 'String' => { 'str' => 'mask' } }, { 'String' => { 'str' => data['rule'] } }], 'args' => change_colname }

          return_column_ref = { 'ResTarget' => { 'name' => name, 'val' => { 'FuncCall' => func } } }
        end
        if data['filter'] != ''
          filter_tables               = {}
          filter_tables[tab['alias']] = tab

          filter_where      = get_filters(filter_tables, data)
          return_column_ref = { 'ResTarget' => { 'name' => name, 'val' => { 'CaseExpr' => { 'args' => [{ 'CaseWhen' => { 'expr' => filter_where[0], 'result' => return_column_ref['ResTarget']['val'] } }], 'defresult' => { 'ColumnRef' => { 'fields' => ref } } } } } }
        end
      end
    end
    return_column_ref
  end

  # @param [Object] table_list
  # @param [Object] where_part
  def get_filters(table_list, where_part = nil)
    filter_w = []
    table_list.each do |alias_name, table|
      filter_list = []
      next if table['schema'].nil?

      if where_part.nil?
        @groups.each do |key, value|
          filter_temp = etcd_data('/sqlfilter/' + @db + '/' + table['schema'] + '/' + table['table'] + key)
          next if filter_temp.empty?
          next if filter_temp['enabled'].to_s == 'false'

          filter_list.push(filter_temp)
        end
        filter_temp = etcd_data('/sqlfilter/' + @db + '/' + table['schema'] + '/' + table['table'] + '/*')

        unless filter_temp.empty?
          filter_list.push(filter_temp) if filter_temp['enabled'].to_s == 'true'
        end
      else
        next unless (@db + '.' + table['schema'] + '.' + table['table']) == where_part['table_column'].split('.')[0...-1].join('.')

        filter_list.push(where_part)
      end
      next if filter_list.count.zero?

      filter_list.each do |filter|
        where_condition = filter['filter'].gsub(table['schema'] + '.' + table['table'], alias_name)
        where_query     = PgQuery.parse('SELECT WHERE ' + where_condition)
        filter_w.push(where_query.tree[0]['RawStmt']['stmt']['SelectStmt']['whereClause'])
      end
    end
    filter_w
  end

  # @param [Object] items
  # @param [Array] table_list
  def parse(items, table_list = [], masked = true)
    old_table_list = []
    return if items.nil?

    if items.is_a?(Hash)
      if items.keys.is_a?(Array)
        items.keys.each do |item|
          case item
          when 'fields'
            @ref               = items[item]
            @return_column_ref = mask(@ref, table_list) if @ref[-1]['A_Star'].nil? && masked == true && @mode == 'select'
            @name              = nil
          when 'ResTarget'
            if @mode == 'update' && masked == true
              masked_field = mask([items[item]['name']], table_list)
              items[item] = { "name" => masked_field[item]['name'], "val" => { "CaseExpr" => { "args" => [{ "CaseWhen" => { "expr" => { "A_Expr" => { "kind" => 0, "name" => [{ "String" => { "str" => "=" } }], "lexpr" => masked_field[item]['val'], "rexpr" => items[item]['val'] } }, "result" => { "ColumnRef" => { "fields" => [items[item]['name']] } } } }], "defresult" => items[item]['val'] } } } unless masked_field.empty?
            end
          when 'name'
            @name = items[item]
          when 'ColumnRef', 'args'
            @remove_ref = 3
          when 'funcname'
            @in_function = 1 if get_string(items[item][0]) == 'count'
          when 'A_Star'
            if @in_function.zero?
              @col_list = {}
              case @ref.count
              when 1
                table_list.each do |alias_name, table|
                  @col_list[alias_name] = table['columns']
                end
              when 2, 3
                alias_name            = get_alias(@ref.first(@ref.count - 1))
                @col_list[alias_name] = table_list[alias_name]['columns'] unless table_list[alias_name].nil?
              else
                raise 'SQL exception check your alias names (' + get_alias(@ref) + ')'
              end
              @remove_ref = 1
            else
              @in_function = 0
            end
          when 'SelectStmt', 'UpdateStmt'
            @mode          = if item == 'UpdateStmt'
                               'update'
                             else
                               'select'
                             end
            old_table_list = table_list
            table_list     = find_table_list(items[item])
            filters        = get_filters(table_list)
          when 'InsertStmt'
            return items
          when 'A_Expr'
            if items[item].is_a?(Hash)
              if items[item].include?('name')
                masked = false unless get_string(items[item]['name'][0]) == '||'
              end
            end
          end


          parse(items[item], table_list, masked)

          masked      = true if item == 'A_Expr'
          @name       = nil if item == 'name'

          @remove_ref = 2 if item == 'ResTarget' && @remove_ref == 1

          if item == 'ResTarget'
            unless items[item].include?('name')
              items[item]['name'] = @change_name unless @change_name.nil?
            end
            @change_name = nil
          end

          if item == 'fields' && @remove_ref == 3 && !@return_column_ref.nil? && @return_column_ref['del'].nil?
            unless @return_column_ref.empty?
              items.delete(item)
              items[item]  = [@return_column_ref['ResTarget']['val']]
              @change_name = @return_column_ref['ResTarget']['name'] if @return_column_ref['ResTarget'].include?('name')
            end
            @return_column_ref = {}
          end

          if item == 'ResTarget' && !@return_column_ref.nil?
            unless @return_column_ref.empty?
              if @return_column_ref['del'].nil?
                items[item] = @return_column_ref['ResTarget']
              else
                items.delete(item)
              end
            end
            @return_column_ref = {}
          end

          if !filters.nil? && item == 'SelectStmt'
            if filters.count > 0
              filters.push(items['SelectStmt']['whereClause']) unless items['SelectStmt']['whereClause'].nil?
              items['SelectStmt']['whereClause'] = { 'BoolExpr' => { 'boolop' => 0, 'args' => filters } }
            end
          end

          table_list = old_table_list if %w[SelectStmt UpdateStmt].include?(item)

        end
      end
    end

    if items.is_a?(Array)
      i = 0
      items.each do |item|
        parse(item, table_list, masked)

        reparse = 0
        unless item.nil?
          if item.empty?
            items.delete_at(i)
            reparse = 1
          end
        end

        if @remove_ref == 2
          k = 1

          @col_list.each do |alias_name, alias_table|
            next if alias_table.nil?

            if alias_table.count > 0 && reparse.zero?
              reparse = 1
              items.delete_at(i)
              k -= 1
            end
            alias_table.each do |col|
              fields = alias_name.split('.').push(col['column_name'])
              items.insert(i + k, 'ResTarget' => { 'val' => { 'ColumnRef' => { 'fields' => fields } } })
              k += 1
            end
          end
          @col_list   = {}
          @remove_ref = 0

        end
        parse(items[i], table_list, masked) if reparse == 1
        i += 1
      end
    end

    items
  end

  def find_table_list(tree, table_list = {})
    key_list = %w[SelectStmt UpdateStmt relation fromClause JoinExpr larg rarg]
    if tree.is_a?(Array)
      tree.each do |k|
        find_table_list(k, table_list)
      end
    else
      tree.keys.each do |key|
        find_table_list(tree[key], table_list) if key_list.include?(key)
      end

      unless tree['RangeVar'].nil?
        table          = {}
        table['table'] = tree['RangeVar']['relname']
        if tree['RangeVar']['schemaname'].nil?
          unless @default_scheme.nil?
            @default_scheme.split(',').each do |scheme|
              scheme           = scheme.strip
              table_defination = get_col_with_table(scheme, table['table'])
              next if table_defination.empty?

              table['schema'] = scheme
              break
            end
          end
        else
          table['schema'] = tree['RangeVar']['schemaname']
        end
        table['alias']             = if tree['RangeVar']['alias'].nil?
                                       if tree['RangeVar']['schemaname'].nil?
                                         table['table']
                                       else
                                         table['schema'] + '.' + table['table']
                                       end
                                     else
                                       tree['RangeVar']['alias']['Alias']['aliasname']
                                     end

        table['columns']           = get_col_with_table(table['schema'], table['table']) unless table['schema'].nil?
        table_list[table['alias']] = table
      end
    end
    table_list
  end
end