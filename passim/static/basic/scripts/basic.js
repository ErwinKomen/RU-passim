var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      ru.basic.init_event_listeners();

      // Initialize Bootstrap popover
      // Note: this is used when hovering over the question mark button
      $('[data-toggle="popover"]').popover();
    });
  });
})(django.jQuery);



// based on the type, action will be loaded

// var $ = django.jQuery.noConflict();

var ru = (function ($, ru) {
  "use strict";

  ru.basic = (function ($, config) {
    // Define variables for ru.basic here
    var loc_divErr = "basic_err",
        loc_urlStore = "",      // Keep track of URL to be shown
        loc_bManuSaved = false,
        dummy = 1;

    // Private methods specification
    var private_methods = {
      /**
       * methodNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      methodNotVisibleFromOutside: function () {
        return "something";
      },
      errClear: function () {
        $("#" + loc_divErr).html("");
      },
      errMsg: function (sMsg, ex) {
        var sHtml = "Error in [" + sMsg + "]<br>";
        if (ex !== undefined && ex !== null) {
          sHtml = sHtml + ex.message;
        }
        $("#" + loc_divErr).html(sHtml);
      }
    }
    // Public methods
    return {
      /**
       * delete_cancel
       *   Hide this <tr> and cancel the delete
       *
       */
      delete_cancel: function (el) {
        try {
          $(el).closest("div.delete-confirm").addClass("hidden");
        } catch (ex) {
          private_methods.errMsg("delete_cancel", ex);
        }
      },

      /**
       * delete_confirm
       *   Open the next <tr> to get delete confirmation (or not)
       *
       */
      delete_confirm: function (el, bNeedConfirm) {
        var elDiv = null;

        try {
          if (bNeedConfirm === undefined) { bNeedConfirm = true; }
          // Action depends on the need for confirmation
          if (bNeedConfirm) {
            // Find the [.delete-row] to be shown
            elDiv = $(el).closest("tr").find(".delete-confirm").first();
            if (elDiv.length === 0) {
              // Try goint to the next <tr>
              elDiv = $(el).closest("tr").next("tr.delete-confirm");
            }
            $(elDiv).removeClass("hidden");
          } else {

          }
        } catch (ex) {
          private_methods.errMsg("delete_confirm", ex);
        }
      },

      /**
       * filter_click
       *    What happens when clicking a badge filter
       *
       */
      filter_click: function (el) {
        var target = null,
            specs = null;

        try {
          target = $(this).attr("targetid");
          if (target !== undefined && target !== null && target !== "") {
            target = $("#" + target);
            // Action depends on checking or not
            if ($(this).hasClass("on")) {
              // it is on, switch it off
              $(this).removeClass("on");
              $(this).removeClass("jumbo-3");
              $(this).addClass("jumbo-1");
              // Must hide it and reset target
              $(target).addClass("hidden");

              // Check if target has a targetid
              specs = $(target).attr("targetid");
              if (specs !== undefined && specs !== "") {
                // Reset related badges
                $(target).find("span.badge").each(function (idx, elThis) {
                  var subtarget = "";

                  $(elThis).removeClass("on");
                  $(elThis).removeClass("jumbo-3");
                  $(elThis).removeClass("jumbo-2");
                  $(elThis).addClass("jumbo-1");
                  subtarget = $(elThis).attr("targetid");
                  if (subtarget !== undefined && subtarget !== "") {
                    $("#" + subtarget).addClass("hidden");
                  }
                });
                // Re-define the target
                target = $("#" + specs);
              }

              $(target).find("input").each(function (idx, elThis) {
                $(elThis).val("");
              });
              // Also reset all select 2 items
              $(target).find("select").each(function (idx, elThis) {
                $(elThis).val("").trigger("change");
              });

            } else {
              // Must show target
              $(target).removeClass("hidden");
              // it is off, switch it on
              $(this).addClass("on");
              $(this).removeClass("jumbo-1");
              $(this).addClass("jumbo-3");
            }

          }
        } catch (ex) {
          private_methods.errMsg("filter_click", ex);
        }
      },

      /**
       * goto_url
       *   Go to the indicated target URL
       *
       */
      goto_url: function (target) {
        try {
          location.href = target;
        } catch (ex) {
          private_methods.errMsg("goto_url", ex);
        }
      },

      /**
       * import_data
       *   Allow user to upload a file
       *
       * Assumptions:
       * - the [el] contains parameter  @targeturl
       * - there is a div 'import_progress'
       * - there is a div 'id_{{ftype}}-{{forloop.counter0}}-file_source'
       *   or one for multiple files: 'id_files_field'
       *
       */
      import_data: function (sKey) {
        var frm = null,
            targeturl = "",
            options = {},
            fdata = null,
            el = null,
            elProg = null,    // Progress div
            elErr = null,     // Error div
            progrurl = null,  // Any progress function to be called
            data = null,
            xhr = null,
            files = null,
            sFtype = "",      // Type of function (cvar, feat, cond)
            elWait = null,
            bDoLoad = false,  // Need to load with a $.get() afterwards
            elInput = null,   // The <input> element with the files
            more = {},        // Additional (json) data to be passed on (from form-data)
            sTargetDiv = "",  // The div where the uploaded reaction comes
            sSaveDiv = "",    // Where to go if saving is needed
            sMsg = "";

        try {
          // The element to use is the key + import_info
          el = $("#" + sKey + "-import_info");
          elProg = $("#" + sKey + "-import_progress");
          elErr = $("#" + sKey + "-import_error");

          // Set the <div> to be used for waiting
          elWait = private_methods.waitInit(el);

          // Get the URL
          targeturl = $(el).attr("targeturl");
          progrurl = $(el).attr("sync-progress");
          sTargetDiv = $(el).attr("targetid");
          sSaveDiv = $(el).attr("saveid");

          if (targeturl === undefined && sSaveDiv !== undefined && sSaveDiv !== "") {
            targeturl = $("#" + sSaveDiv).attr("ajaxurl");
            sTargetDiv = $("#" + sSaveDiv).attr("openid");
            sFtype = $(el).attr("ftype");
            bDoLoad = true;
          }

          if ($(el).is("input")) {
            elInput = el;
          } else {
            elInput = $(el).find("input").first();
          }

          // Show progress
          $(elProg).attr("value", "0");
          $(elProg).removeClass("hidden");
          if (bDoLoad) {
            $(".save-warning").html("loading the definition..." + loc_sWaiting);
            $(".submit-row button").prop("disabled", true);
          }

          // Add data from the <form> nearest to me: 
          frm = $(el).closest("form");
          if (frm !== undefined) { data = $(frm).serializeArray(); }

          for (var i = 0; i < data.length; i++) {
            more[data[i]['name']] = data[i]['value'];
          }
          // Showe the user needs to wait...
          private_methods.waitStart(elWait);

          // Now initiate any possible progress calling
          if (progrurl !== null) {
            loc_progr = [];
            window.setTimeout(function () { ru.basic.check_progress(progrurl, sTargetDiv); }, 2000);
          }

          // Upload XHR
          $(elInput).upload(targeturl,
            more,
            function (response) {
              // Transactions have been uploaded...
              console.log("done: ", response);

              // Show where we are
              $(el).addClass("hidden");
              $(".save-warning").html("saving..." + loc_sWaiting);

              // First leg has been done
              if (response === undefined || response === null || !("status" in response)) {
                private_methods.errMsg("No status returned");
              } else {
                switch (response.status) {
                  case "ok":
                    // Check how we should react now
                    if (bDoLoad) {
                      // Show where we are
                      $(".save-warning").html("retrieving..." + loc_sWaiting);

                      $.get(targeturl, function (response) {
                        if (response === undefined || response === null || !("status" in response)) {
                          private_methods.errMsg("No status returned");
                        } else {
                          switch (response.status) {
                            case "ok":
                              // Show the response in the appropriate location
                              $("#" + sTargetDiv).html(response.html);
                              $("#" + sTargetDiv).removeClass("hidden");
                              break;
                            default:
                              // Check how/what to show
                              if ("err_view" in response) {
                                private_methods.errMsg(response['err_view']);
                              } else if ("error_list" in response) {
                                private_methods.errMsg(response['error_list']);
                              } else {
                                // Just show the HTML
                                $("#" + sTargetDiv).html(response.html);
                                $("#" + sTargetDiv).removeClass("hidden");
                              }
                              break;
                          }
                          // Make sure events are in place again
                          ru.basic.init_events();
                          switch (sFtype) {
                            case "cvar":
                              ru.basic.init_cvar_events();
                              break;
                            case "cond":
                              ru.basic.init_cond_events();
                              break;
                            case "feat":
                              ru.basic.init_feat_events();
                              break;
                          }
                          // Indicate we are through with waiting
                          private_methods.waitStop(elWait);
                        }
                      });
                    } else {
                      // Remove all project-part class items
                      $(".project-part").addClass("hidden");
                      // Place the response here
                      $("#" + sTargetDiv).html(response.html);
                      $("#" + sTargetDiv).removeClass("hidden");
                    }
                    break;
                  default:
                    // Check WHAT to show
                    sMsg = "General error (unspecified)";
                    if ("err_view" in response) {
                      sMsg = response['err_view'];
                    } else if ("error_list" in response) {
                      sMsg = response['error_list'];
                    } else {
                      // Indicate that the status is not okay
                      sMsg = "Status is not good. It is: " + response.status;
                    }
                    // Show the message at the appropriate location
                    $(elErr).html("<div class='error'>" + sMsg + "</div>");
                    // Make sure events are in place again
                    ru.basic.init_events();
                    switch (sFtype) {
                      case "cvar":
                        ru.basic.init_cvar_events();
                        break;
                      case "cond":
                        ru.basic.init_cond_events();
                        break;
                      case "feat":
                        ru.basic.init_feat_events();
                        break;
                    }
                    // Indicate we are through with waiting
                    private_methods.waitStop(elWait);
                    $(".save-warning").html("(not saved)");
                    break;
                }
              }
              private_methods.waitStop(elWait);
            }, function (progress, value) {
              // Show  progress of uploading to the user
              console.log(progress);
              $(elProg).val(value);
            }
          );
          // Hide progress after some time
          setTimeout(function () { $(elProg).addClass("hidden"); }, 1000);

          // Indicate waiting can stop
          private_methods.waitStop(elWait);
        } catch (ex) {
          private_methods.errMsg("import_data", ex);
          private_methods.waitStop(elWait);
        }
      },

      /**
       *  init_events
       *      Bind main necessary events
       *
       */
      init_events: function (sUrlShow, options) {
        var lHtml = [],
            elA = null,
            object_id = "",
            targetid = null,
            sHtml = "";

        try {
          $(".ms.editable a").unbind("click").click(ru.basic.manu_edit);

          // Switch filters
          $(".badge.filter").unbind("click").click(ru.basic.filter_click);

          // Look for options
          if (options !== undefined) {
            // Evaluate that object
            if ('isnew' in options && options['isnew']) {
              // Make sure the 'new' is triggered
              $(".edit-mode").removeClass("hidden");
              $(".view-mode").addClass("hidden");
              // This is 'new', so don't show buttons cancel and delete
              $("a[mode='cancel'], a[mode='delete']").addClass("hidden");
              // Since this is new, don't show fields that may not be shown for new
              $(".edit-notnew").addClass("hidden");
              $(".edit-new").removeClass("hidden");
            }
          }

          // Make sure select2 is initialized correctly
          // NOTE: what about select2_options?
          //    $(".django-select2").djangoSelect2(select2_options);
          $(".django-select2").djangoSelect2();

        } catch (ex) {
          private_methods.errMsg("init_event_listeners", ex);
        }
      },

      /**
       * init_typeahead
       *    Initialize the typeahead features, based on the existing bloodhound stuff
       */
      init_typeahead: function () {
        try {
          // First destroy them
          $(".typeahead.keywords").typeahead('destroy');
          $(".typeahead.languages").typeahead('destroy');


          // Type-ahead: KEYWORD -- NOTE: not in a form-row, but in a normal 'row'
          $(".row .typeahead.keywords, tr .typeahead.keywords").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            {
              name: 'keywords', source: loc_keyword, limit: 25, displayKey: "name",
              templates: {
                empty: '<p>Use the wildcard * to mark an inexact wording of a keyword</p>',
                suggestion: function (item) {
                  return '<div>' + item.name + '</div>';
                }
              }
            }
          ).on('typeahead:selected typeahead:autocompleted', function (e, suggestion, name) {
            $(this).closest("td").find(".keyword-key input").last().val(suggestion.id);
          });

          // Type-ahead: LANGUAGE -- NOTE: not in a form-row, but in a normal 'row'
          $(".row .typeahead.languages, tr .typeahead.languages").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            {
              name: 'languages', source: loc_language, limit: 25, displayKey: "name",
              templates: {
                empty: '<p>Use the wildcard * to mark an inexact wording of a language</p>',
                suggestion: function (item) {
                  return '<div>' + item.name + '</div>';
                }
              }
            }
          ).on('typeahead:selected typeahead:autocompleted', function (e, suggestion, name) {
            $(this).closest("td").find(".language-key input").last().val(suggestion.id);
          });

          // Make sure we know which element is pressed in typeahead
          $(".form-row:not(.empty-form) .typeahead").on("keyup",
            function () {
              loc_elInput = $(this);
            });

          // Allow "Search on ENTER" from typeahead fields
          $(".form-row:not(.empty-form) .searching").on("keypress",
            function (evt) {
              var key = evt.which,  // Get the KEY information
                  start = null,
                  button = null;

              // Look for ENTER
              if (key === KEYS.ENTER) {
                // Find the 'Search' button
                button = $(this).closest("form").find("a[role=button]").last();
                // Check for the inner text
                if ($(button)[0].innerText === "Search") {
                  // Found it
                  $(button).click();
                  evt.preventDefault();
                }
              }
            });

          // Make sure the twitter typeahead spans are maximized
          $("span.twitter-typeahead").each(function () {
            var style = $(this).attr("style");
            $(this).attr("style", style + " width: 100%;");
          });

        } catch (ex) {
          private_methods.errMsg("init_typeahead", ex);
        }
      },

      /**
       * manu_edit
       *   Switch between edit modes on this <tr>
       *   And if saving is required, then call the [targeturl] to send a POST of the form data
       *
       */
      manu_edit: function (el, sType, oParams) {
        var //el = this,
            sMode = "",
            colspan = "",
            targeturl = "",
            targetid = "",
            afterurl = "",
            targethead = null,
            lHtml = [],
            data = null,
            key = "",
            i = 0,
            frm = null,
            bOkay = true,
            bReloading = false,
            manutype = "",
            err = "#little_err_msg",
            elTr = null,
            elView = null,
            elEdit = null;

        try {
          // Possibly correct [el]
          if (el !== undefined && "currentTarget" in el) { el = el.currentTarget; }
          // Get the mode
          if (sType !== undefined && sType !== "") {
            sMode = sType;
          } else {
            sMode = $(el).attr("mode");
          }
          // Get the <tr>
          elTr = $(el).closest("td");
          // Get the manutype
          manutype = $(el).attr("manutype");
          if (manutype === undefined) { manutype = "other"; }

          // Get alternative parameters from [oParams] if this is defined
          if (oParams !== undefined) {
            if ('manutype' in oParams) { manutype = oParams['manutype']; }
          }

          // Check if we need to take the table
          if ($(elTr).hasClass("table")) {
            elTr = $(el).closest("table");
          }
          // Get the view and edit values
          elView = $(el).find(".view-mode").first();
          elEdit = $(el).find(".edit-mode").first();

          // Action depends on the mode
          switch (sMode) {
            case "skip":
              return;
              break;
            case "edit":
              // Make sure all targetid's that need opening are shown
              $(elTr).find(".view-mode:not(.hidden)").each(function () {
                var elTarget = $(this).attr("targetid");
                var targeturl = $(this).attr("targeturl");

                frm = $(el).closest("form");
                data = frm.serializeArray();
                if (elTarget !== undefined && elTarget !== "") {
                  // Do we have a targeturl?
                  if (targeturl !== undefined && targeturl !== "") {
                    // Make a post to the targeturl
                    $.post(targeturl, data, function (response) {
                      // Action depends on the response
                      if (response === undefined || response === null || !("status" in response)) {
                        private_methods.errMsg("No status returned");
                      } else {
                        switch (response.status) {
                          case "ready":
                          case "ok":
                            if ("html" in response) {
                              // Show the HTML in the targetid
                              $("#" + elTarget).html(response['html']);
                            }
                            // In all cases: open the target
                            $("#" + elTarget).removeClass("hidden");
                            // And make sure typeahead works
                            ru.basic.init_typeahead();
                            break;
                        }
                      }
                    });
                  } else {
                    // Just open the target
                    $("#" + elTarget).removeClass("hidden");
                  }
                }
              });
              // Go to edit mode
              $(elTr).find(".view-mode").addClass("hidden");
              $(elTr).find(".edit-mode").removeClass("hidden");
              // Make sure typeahead works here
              ru.basic.init_typeahead();
              break;
            case "view":
            case "new":
              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");
              targetid = $(el).attr("targetid");
              // If the targetid is specified, we need to get it from there
              if (targetid === undefined || targetid === "") {
                // No targetid specified: just open the target url
                window.location.href = targeturl;
              } else if (loc_bManuSaved) {
                loc_bManuSaved = false;
                // Refresh page
                window.location.href = window.location.href;
              } else {
                switch (manutype) {
                  case "goldlink":
                  case "goldnew":
                  case "newgoldlink":
                    targethead = $("#" + targetid);
                    break;
                  case "goldlinkclose":
                    targethead = $("#" + targetid).closest(".goldlink");
                    $(targethead).addClass("hidden");
                    $(elTr).find(".edit-mode").addClass("hidden");
                    $(elTr).find(".view-mode").removeClass("hidden");
                    return;
                  default:
                    targethead = $("#" + targetid).closest("tr.gold-head");
                    if (targethead !== undefined && targethead.length > 0) {
                      // Targetid is specified: check if we need to close
                      if (!$(targethead).hasClass("hidden")) {
                        // Close it
                        $(targethead).addClass("hidden");
                        return;
                      }
                    } else if ($("#" + targetid).attr("showing") !== undefined) {
                      if ($("#" + targetid).attr("showing") === "true") {
                        $("#" + targetid).attr("showing", "false");
                        $("#" + targetid).html("");
                        return;
                      }
                    }
                    break;
                }

                // There is a targetid specified, so make a GET request for the information and get it here
                data = [];
                // Check if there are any parameters in [oParams]
                if (oParams !== undefined) {
                  for (key in oParams) {
                    data.push({ 'name': key, 'value': oParams[key] });
                  }
                }

                $.get(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "ready":
                      case "ok":
                      case "error":
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $("#" + targetid).html(response['html']);
                          // Make sure invisible ancestors show up
                          $("#" + targetid).closest(".hidden").removeClass("hidden");
                          // Indicate that we are showing here
                          $("#" + targetid).attr("showing", "true");

                          switch (manutype) {
                            case "goldsermon":
                              // Close any other edit-mode items
                              $(targethead).closest("table").find(".edit-mode").addClass("hidden");
                              // Open this particular edit-mode item
                              $(targethead).removeClass("hidden");
                              break;
                            case "goldlink":
                              $(el).closest("table").find(".edit-mode").addClass("hidden");
                              $(el).closest("table").find(".view-mode").removeClass("hidden");
                              $(elTr).find(".edit-mode").removeClass("hidden");
                              $(elTr).find(".view-mode").addClass("hidden");
                              break;
                            case "goldnew":
                              // Use the new standard approach for *NEW* elements
                              $("#" + targetid).closest(".subform").find(".edit-mode").removeClass("hidden");
                              $("#" + targetid).closest(".subform").find(".view-mode").addClass("hidden");
                              break;
                            default:
                              break;
                          }

                          // Check on specific modes
                          if (sMode === "new") {
                            $("#" + targetid).find(".edit-mode").removeClass("hidden");
                            $("#" + targetid).find(".view-mode").addClass("hidden");
                            // This is 'new', so don't show buttons cancel and delete
                            $("#" + targetid).find("a[mode='cancel'], a[mode='delete']").addClass("hidden");
                            // Since this is new, don't show fields that may not be shown for new
                            $("#" + targetid).find(".edit-notnew").addClass("hidden");
                            $("#" + targetid).find(".edit-new").removeClass("hidden");
                          } else {
                            // Just viewing means we can also delete...
                            // What about CANCEL??
                            // $("#" + targetid).find("a[mode='delete']").addClass("hidden");
                          }

                          // If there is an error, indicate this
                          if (response.status === "error") {
                            if ("msg" in response) {
                              if (typeof response['msg'] === "object") {
                                lHtml = []
                                lHtml.push("Errors:");
                                $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                                $(err).html(lHtml.join("<br />"));
                              } else {
                                $(err).html("Error: " + response['msg']);
                              }
                            } else {
                              $(err).html("<code>There is an error</code>");
                            }
                          }
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  switch (manutype) {
                    case "goldlink":
                    case "goldnew":
                      break;
                    default:
                      // Return to view mode
                      $(elTr).find(".view-mode").removeClass("hidden");
                      $(elTr).find(".edit-mode").addClass("hidden");
                      // Hide waiting symbol
                      $(elTr).find(".waiting").addClass("hidden");
                      break;
                  }
                  // Perform init again
                  ru.basic.init_typeahead();
                  ru.basic.init_events();
                });

              }
              break;
            case "save":
              // Do we have an afterurl?
              afterurl = $(el).attr("afterurl");

              // Show waiting symbol
              $(elTr).find(".waiting").removeClass("hidden");

              // Make sure we know where the error message should come
              if ($(err).length === 0) { err = $(".err-msg").first(); }

              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");
              targetid = $(el).attr("targetid");

              // What if no targetid is specified?
              if (targetid === undefined || targetid === "") {
                // Then we need the parent of our closest enclosing table
                targetid = $(el).closest("form").parent();
              } else {
                targetid = $("#" + targetid);
              }

              // Check
              if (targeturl === undefined) { $(err).html("Save: no <code>targeturl</code> specified"); bOkay = false }
              if (bOkay && targetid === undefined) { $(err).html("Save: no <code>targetid</code> specified"); }

              // Get the form data
              frm = $(el).closest("form");
              if (bOkay && frm === undefined) { $(err).html("<i>There is no <code>form</code> in this page</i>"); }

              // Either POST the request
              if (bOkay) {
                // Get the data into a list of k-v pairs
                data = $(frm).serializeArray();
                // Adapt the value for the [library] based on the [id] 
                // Try to save the form data: send a POST
                $.post(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "error":
                        // Indicate there is an error
                        bOkay = false;
                        // Show the error in an appropriate place
                        if ("msg" in response) {
                          if (typeof response['msg'] === "object") {
                            lHtml = [];
                            lHtml.push("Errors:");
                            $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                            $(err).html(lHtml.join("<br />"));
                          } else {
                            $(err).html("Error: " + response['msg']);
                          }
                        } else if ("errors" in response) {
                          lHtml = [];
                          lHtml.push("<h4>Errors</h4>");
                          for (i = 0; i < response['errors'].length; i++) {
                            $.each(response['errors'][i], function (key, value) {
                              lHtml.push("<b>" + key + "</b>: </i>" + value + "</i>");
                            });
                          }
                          $(err).html(lHtml.join("<br />"));
                        } else if ("error_list" in response) {
                          lHtml = [];
                          lHtml.push("Errors:");
                          $.each(response['error_list'], function (key, value) { lHtml.push(key + ": " + value); });
                          $(err).html(lHtml.join("<br />"));
                        } else {
                          $(err).html("<code>There is an error</code>");
                        }
                        break;
                      case "ready":
                      case "ok":
                        // First check for afterurl
                        if (afterurl !== undefined && afterurl !== "") {
                          // Make sure we go to the afterurl
                          window.location = afterurl;
                        }
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $(targetid).html(response['html']);
                          // Signal globally that something has been saved
                          loc_bManuSaved = true;
                          // If an 'afternewurl' is specified, go there
                          if ('afternewurl' in response && response['afternewurl'] !== "") {
                            window.location = response['afternewurl'];
                            bReloading = true;
                          } else {
                            // nothing else yet
                          }
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  if (!bReloading && bOkay) {
                    // Return to view mode
                    $(elTr).find(".view-mode").removeClass("hidden");
                    $(elTr).find(".edit-mode").addClass("hidden");
                    // Hide waiting symbol
                    $(elTr).find(".waiting").addClass("hidden");
                    // Perform init again
                    ru.basic.init_events();
                  }
                });
              } else {
                // Or else stop waiting - with error message above
                $(elTr).find(".waiting").addClass("hidden");
              }

              break;
            case "cancel":
              // Make sure all targetid's that need closing are hidden
              $(elTr).find(".edit-mode:not(.hidden)").each(function () {
                var elTarget = $(this).attr("targetid");
                if (elTarget !== undefined && elTarget !== "") {
                  $("#" + elTarget).addClass("hidden");
                }
              });
              // Go to view mode without saving
              $(elTr).find(".view-mode").removeClass("hidden");
              $(elTr).find(".edit-mode").addClass("hidden");
              break;
            case "delete":
              // Do we have an afterurl?
              afterurl = $(el).attr("afterurl");

              // Check if we are under a delete-confirm
              if ($(el).closest("div[delete-confirm]").length === 0) {
                // Ask for confirmation
                // NOTE: we cannot be more specific than "item", since this can be manuscript or sermongold
                if (!confirm("Do you really want to remove this item?")) {
                  // Return from here
                  return;
                }
              }
              // Show waiting symbol
              $(elTr).find(".waiting").removeClass("hidden");

              // Get any possible targeturl
              targeturl = $(el).attr("targeturl");

              // Determine targetid from own
              targetid = $(el).closest(".gold-head");
              targethead = $(targetid).prev();

              // Check
              if (targeturl === undefined) { $(err).html("Save: no <code>targeturl</code> specified"); bOkay = false }

              // Get the form data
              frm = $(el).closest("form");
              if (bOkay && frm === undefined) { $(err).html("<i>There is no <code>form</code> in this page</i>"); }
              // Either POST the request
              if (bOkay) {
                // Get the data into a list of k-v pairs
                data = $(frm).serializeArray();
                // Add the delete mode
                data.push({ name: "action", value: "delete" });

                // Try to delete: send a POST
                $.post(targeturl, data, function (response) {
                  // Action depends on the response
                  if (response === undefined || response === null || !("status" in response)) {
                    private_methods.errMsg("No status returned");
                  } else {
                    switch (response.status) {
                      case "ready":
                      case "ok":
                        // Do we have afterdelurl afterurl?
                        // If an 'afternewurl' is specified, go there
                        if ('afterdelurl' in response && response['afterdelurl'] !== "") {
                          window.location = response['afterdelurl'];
                        } else if (afterurl === undefined || afterurl === "") {
                          // Delete visually
                          $(targetid).remove();
                          $(targethead).remove();
                        } else {
                          // Make sure we go to the afterurl
                          window.location = afterurl;
                        }
                        break;
                      case "error":
                        if ("html" in response) {
                          // Show the HTML in the targetid
                          $(err).html(response['html']);
                          // If there is an error, indicate this
                          if (response.status === "error") {
                            if ("msg" in response) {
                              if (typeof response['msg'] === "object") {
                                lHtml = []
                                lHtml.push("Errors:");
                                $.each(response['msg'], function (key, value) { lHtml.push(key + ": " + value); });
                                $(err).html(lHtml.join("<br />"));
                              } else {
                                $(err).html("Error: " + response['msg']);
                              }
                            } else {
                              $(err).html("<code>There is an error</code>");
                            }
                          }
                        } else {
                          // Send a message
                          $(err).html("<i>There is no <code>html</code> in the response from the server</i>");
                        }
                        break;
                      default:
                        // Something went wrong -- show the page or not?
                        $(err).html("The status returned is unknown: " + response.status);
                        break;
                    }
                  }
                  // Return to view mode
                  $(elTr).find(".view-mode").removeClass("hidden");
                  $(elTr).find(".edit-mode").addClass("hidden");
                  // Hide waiting symbol
                  $(elTr).find(".waiting").addClass("hidden");
                  // Perform init again
                  ru.basic.init_events();
                });
              } else {
                // Or else stop waiting - with error message above
                $(elTr).find(".waiting").addClass("hidden");
              }


              break;
          }
        } catch (ex) {
          private_methods.errMsg("manu_edit", ex);
        }
      },

      /**
        * result_download
        *   Trigger creating and downloading a result CSV / XLSX / JSON
        *
        */
      post_download: function (elStart) {
        var ajaxurl = "",
            contentid = null,
            response = null,
            frm = null,
            el = null,
            sHtml = "",
            oBack = null,
            dtype = "",
            sMsg = "",
            method = "normal",
            data = [];

        try {
          // Clear the errors
          private_methods.errClear();

          // obligatory parameter: ajaxurl
          ajaxurl = $(elStart).attr("ajaxurl");
          contentid = $(elStart).attr("contentid");

          // Gather the information
          frm = $(elStart).closest(".container-small").find("form");
          if (frm.length === 0) {
            frm = $(elStart).closest("td").find("form");
            if (frm.length === 0) {
              frm = $(elStart).closest(".body-content").find("form");
              if (frm.length === 0) {
                frm = $(elStart).closest(".container-large.body-content").find("form");
              }
            }
          }
          // Check what we have
          if (frm === null || frm.length === 0) {
            // Didn't find the form
            private_methods.errMsg("post_download: could not find form");
          } else {
            // Make sure we take only the first matching form
            frm = frm.first();
          }
          // Get the download type and put it in the <input>
          dtype = $(elStart).attr("downloadtype");
          $(frm).find("#downloadtype").val(dtype);

          switch (method) {
            case "erwin":
              data = frm.serialize();
              $.post(ajaxurl, data, function (response) {
                var iready = 1;
              });
              break;
            default:
              // Set the 'action; attribute in the form
              frm.attr("action", ajaxurl);
              // Make sure we do a POST
              frm.attr("method", "POST");

              // Do we have a contentid?
              if (contentid !== undefined && contentid !== null && contentid !== "") {
                // Process download data
                switch (dtype) {
                  default:
                    // TODO: add error message here
                    return;
                }
              } else {
                // Do a plain submit of the form
                oBack = frm.submit();
              }
              break;
          }

          // Check on what has been returned
          if (oBack !== null) {

          }
        } catch (ex) {
          private_methods.errMsg("post_download", ex);
        }
      },

      /**
       * search_reset
       *    Clear the information in the form's fields and then do a submit
       *
       */
      search_reset: function (elStart) {
        var frm = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Clear the information in the form's INPUT fields
          $(frm).find("input:not([readonly]).searching").val("");
          // Show we are waiting
          $("#waitingsign").removeClass("hidden");
          // Now submit the form
          frm.submit();
        } catch (ex) {
          private_methods.errMsg("search_reset", ex);
        }
      },

      /**
       * search_clear
       *    No real searching, just reset the criteria
       *
       */
      search_clear: function (elStart) {
        var frm = null,
            idx = 0,
            lFormRow = [];

        try {
          // Clear filters
          $(".badge.filter").each(function (idx, elThis) {
            var target;

            target = $(elThis).attr("targetid");
            if (target !== undefined && target !== null && target !== "") {
              target = $("#" + target);
              // Action depends on checking or not
              if ($(elThis).hasClass("on")) {
                // it is on, switch it off
                $(elThis).removeClass("on");
                $(elThis).removeClass("jumbo-3");
                $(elThis).addClass("jumbo-1");
                // Must hide it and reset target
                $(target).addClass("hidden");
                $(target).find("input").each(function (idx, elThis) {
                  $(elThis).val("");
                });
                // Also reset all select 2 items
                $(target).find("select").each(function (idx, elThis) {
                  $(elThis).val("").trigger("change");
                });
              }
            }
          });

        } catch (ex) {
          private_methods.errMsg("search_clear", ex);
        }
      },

      /**
       * search_start
       *    Gather the information in the form's fields and then do a submit
       *
       */
      search_start: function (elStart, method, iPage) {
        var frm = null,
            url = "",
            targetid = null,
            targeturl = "",
            data = null;

        try {
          // Get to the form
          frm = $(elStart).closest('form');
          // Get the data from the form
          data = frm.serializeArray();

          // Determine the method
          if (method === undefined) { method = "submit"; }

          // Get the URL from the form
          url = $(frm).attr("action");

          // Action depends on the method
          switch (method) {
            case "submit":
              // Show we are waiting
              $("#waitingsign").removeClass("hidden");
              // Store the current URL
              loc_urlStore = url;
              // If there is a page number, we need to process it
              if (iPage !== undefined) {
                $(elStart).find("input[name=page]").each(function (el) {
                  $(this).val(iPage);
                });
              }
              // Now submit the form
              frm.submit();
              break;
            case "post":
              // Determine the targetid
              targetid = $(elStart).attr("targetid");
              if (targetid == "subform") {
                targetid = $(elStart).closest(".subform");
              } else {
                targetid = $("#" + targetid);
              }
              // Get the targeturl
              targeturl = $(elStart).attr("targeturl");

              // Get the page we need to go to
              if (iPage === undefined) { iPage = 1; }
              data.push({ 'name': 'page', 'value': iPage });

              // Issue a post
              $.post(targeturl, data, function (response) {
                // Action depends on the response
                if (response === undefined || response === null || !("status" in response)) {
                  private_methods.errMsg("No status returned");
                } else {
                  switch (response.status) {
                    case "ready":
                    case "ok":
                      // Show the HTML target
                      $(targetid).html(response['html']);
                      // Possibly do some initialisations again??

                      // Make sure events are re-established
                      // ru.basic.init_events();
                      ru.basic.init_typeahead();
                      break;
                    case "error":
                      // Show the error
                      if ('msg' in response) {
                        $(targetid).html(response.msg);
                      } else {
                        $(targetid).html("An error has occurred");
                      }
                      break;
                  }
                }
              });


              break;
          }

        } catch (ex) {
          private_methods.errMsg("search_start", ex);
        }
      },

      /**
       * search_ordered_start
       *    Perform a simple 'submit' call to search_start
       *
       */
      search_ordered_start: function (order) {
        var elStart = null;

        try {
          // And then go to the first element within the form that is of any use
          elStart = $(".search_ordered_start").first();
          ru.passim.seeker.search_start(elStart, 'submit', 1, order)
        } catch (ex) {
          private_methods.errMsg("search_ordered_start", ex);
        }
      },

      /**
       * search_paged_start
       *    Perform a simple 'submit' call to search_start
       *
       */
      search_paged_start: function (iPage) {
        var elStart = null;

        try {
          // And then go to the first element within the form that is of any use
          elStart = $(".search_paged_start").first();
          ru.basic.search_start(elStart, 'submit', iPage)
        } catch (ex) {
          private_methods.errMsg("search_paged_start", ex);
        }
      },

      /**
       * toggle_click
       *   Action when user clicks an element that requires toggling a target
       *
       */
      toggle_click: function (elThis, class_to_close) {
        var elGroup = null,
            elTarget = null,
            sStatus = "";

        try {
          // Get the target to be opened
          elTarget = $(elThis).attr("targetid");
          // Sanity check
          if (elTarget !== null) {
            // Show it if needed
            if ($("#" + elTarget).hasClass("hidden")) {
              $("#" + elTarget).removeClass("hidden");
            } else {
              $("#" + elTarget).addClass("hidden");
              // Check if there is an additional class to close
              if (class_to_close !== undefined && class_to_close !== "") {
                $("." + class_to_close).addClass("hidden");
              }
            }
          }
        } catch (ex) {
          private_methods.errMsg("toggle_click", ex);
        }
      }


      // LAST POINT
    }
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

