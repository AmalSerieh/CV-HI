#!/usr/bin/env sh

load_local_environment() {
    env_file="${1:-.env}"
    [ -f "$env_file" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
            ''|'#'*) continue ;;
            [A-Za-z_]*=*) ;;
            *) continue ;;
        esac
        key=${line%%=*}
        value=${line#*=}
        case "$value" in
            \"*\") value=${value#\"}; value=${value%\"} ;;
            \'*\') value=${value#\'}; value=${value%\'} ;;
        esac
        eval "current=\${$key+x}"
        [ "$current" = x ] || export "$key=$value"
    done < "$env_file"
}
