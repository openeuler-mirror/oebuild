complete -F _myobj_complete_func oebuild
_myobj_complete_func() {
    COMPREPLY=()
    command_name="${COMP_WORDS[COMP_CWORD]}"
    secondary_command_name="${COMP_WORDS[COMP_CWORD-1]}"
    completion_txt="init update generate bitbake manifest clear runqemu menv deploy-target undeploy-target mplugin"
    case "${secondary_command_name}" in oebuild)
       COMPREPLY=($(compgen -W "${completion_txt}" -- ${command_name}))
    esac
    case "${secondary_command_name}" in 
      menv)
      secondary_command="create list activate remove"
       COMPREPLY=($(compgen -W "${secondary_command}" ${command_name}))
        return 0
        ;;
      mplugin)
      secondary_command="install list enable disable remove"
       COMPREPLY=($(compgen -W "${secondary_command}" ${command_name}))
        return 0
        ;;
    esac
    return 0
}
