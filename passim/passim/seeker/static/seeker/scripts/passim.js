var django = {
  "jQuery": jQuery.noConflict(true)
};
var jQuery = django.jQuery;
var $ = jQuery;

(function ($) {
  $(function () {
    $(document).ready(function () {
      // Initialize event listeners
      ru.passim.init_event_listeners();
      $('#id_subtype >option').show();
      // Add 'copy' action to inlines
      ru.passim.tabinline_add_copy();
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

  ru.passim = (function ($, config) {
    // Define variables for ru.collbank here
    var loc_example = "",
        loc_divErr = "passim_err",
        loc_countries = [],
        loc_countriesL = [],
        loc_cities = [],
        loc_citiesL = [],
        loc_libraries = [],
        loc_librariesL = [],
        loc_authors = [],
        loc_authorsL = [],
        loc_elInput = null,
        loc_sWaiting = " <span class=\"glyphicon glyphicon-refresh glyphicon-refresh-animate\"></span>",
        loc_cnrs_manu_url = "http://medium-avance.irht.cnrs.fr/Manuscrits/manuscritforetablissement",
        base_url = "",
        oSyncTimer = null;


    // Private methods specification
    var private_methods = {
      /**
       * methodNotVisibleFromOutside - example of a private method
       * @returns {String}
       */
      methodNotVisibleFromOutside: function () {
        return "something";
      },
      errClear: function() {
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
       * init_event_listeners
       *    Initialize eent listeners for this module
       */
      init_event_listeners: function () {
        // Get the base URL
        base_url = $("#__baseurl__").text();

        // Bloodhound: COUNTRY
        loc_countries = new Bloodhound({
          datumTokenizer: Bloodhound.tokenizers.whitespace,
          queryTokenizer: Bloodhound.tokenizers.whitespace,
          // loc_countries will be an array of countries
          // local: loc_countries,
          prefetch: { url: base_url + 'api/countries/', cache: true },
          remote:   { url: base_url + 'api/countries/?country=%QUERY', wildcard: '%QUERY' }
        });

        // Bloodhound: CITY
        loc_cities = new Bloodhound({
          datumTokenizer: Bloodhound.tokenizers.whitespace,
          queryTokenizer: Bloodhound.tokenizers.whitespace,
          // loc_countries will be an array of countries
          // local: loc_cities,
          prefetch: { url: base_url + 'api/cities/', cache: true },
          remote: {
            url: base_url + 'api/cities/?city=',
            replace: ru.passim.tt_city
          }
        });

        // Bloodhound: LIBRARY
        loc_libraries = new Bloodhound({
          datumTokenizer: Bloodhound.tokenizers.whitespace,
          queryTokenizer: Bloodhound.tokenizers.whitespace,
          // loc_libraries will be an array of libraries
          local: loc_librariesL,
          prefetch: { url: base_url + 'api/libraries/', cache: true },
          remote: {
            url: base_url + 'api/libraries/?library=',
            replace: ru.passim.tt_library
          }
        });

        // Bloodhound: AUTHOR
        loc_authors = new Bloodhound({
          datumTokenizer: function (myObj) {
            return myObj;
          },
          queryTokenizer: function (myObj) {
            return myObj;
          },
          // loc_countries will be an array of countries
          local: loc_authorsL,
          prefetch: { url: base_url + 'api/authors/list/', cache: true },
          remote: {
            url: base_url + 'api/authors/list/?name=',
            replace: function (url, uriEncodedQuery) {
              url += encodeURIComponent(uriEncodedQuery);
              return url;
            }
          }
        });

        // Initialize typeahead
        ru.passim.init_typeahead();

      },

      /**
       * init_typeahead
       *    Initialize the typeahead features, based on the existing bloodhound stuff
       */
      init_typeahead: function () {
        try {
          // First destroy them
          $(".typeahead.countries").typeahead('destroy');
          $(".typeahead.cities").typeahead('destroy');
          $(".typeahead.libraries").typeahead('destroy');
          $(".typeahead.authors").typeahead('destroy');

          // Type-ahead: COUNTRY
          $(".form-row:not(.empty-form) .typeahead.countries, .manuscript-details .typeahead.countries").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            { name: 'countries', source: loc_countries, limit: 20,
              display: function (item) { return item.name; },
              templates: { suggestion: function (item) { return '<div>' + item.name + '</div>'; } }
            }
          );
          // Type-ahead: CITY
          $(".form-row:not(.empty-form) .typeahead.cities, .manuscript-details .typeahead.cities").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            { name: 'cities', source: loc_cities, limit: 25,
              display: function (item) { return item.name; },
              templates: { suggestion: function (item) { return '<div>' + item.name + '</div>'; } }
            }
          );
          // Type-ahead: LIBRARY
          $(".form-row:not(.empty-form) .typeahead.libraries, .manuscript-details .typeahead.libraries").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            { name: 'libraries', source: loc_libraries, limit: 25,
              display: function (item) { return item.name; },
              templates: { suggestion: function (item) { return '<div>' + item.name + '</div>'; } }
            }
          );

          // Type-ahead: AUTHOR -- NOTE: not in a form-row, but in a normal 'row'
          $(".row .typeahead.authors").typeahead(
            { hint: true, highlight: true, minLength: 1 },
            {
              name: 'authors', source: loc_authors, limit: 10,
              display: function (item) { return item.name; },
              templates: {
                empty: '<p>Not found</p>',
                suggestion: function (item) {
                  return '<div>' + item.name + '</div>';
                }
              }
            }
          );

          // Make sure we know which element is pressed in typeahead
          $(".form-row:not(.empty-form) .typeahead").on("keyup", function () { loc_elInput = $(this); });

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
       *  tt_country
       *    Bloodhound / remote / replace function for: COUNTRY
       */
      tt_country: function (url, uriEncodedQuery) {
        var elThis = this;

        try {

        } catch (ex) {
          private_methods.errMsg("tt_country", ex);
        }
      },

      /**
       *  tt_city
       *    Bloodhound / remote / replace function for: CITY
       */
      tt_city: function (url, uriEncodedQuery) {
        var elThis = loc_elInput,
            elRow = null,
            sPrefix = "id_",
            country = "";

        try {
          // Get to this row
          elRow = $(elThis).closest("tr").first();
          if (elRow.length > 0) {
            // Get the PREFIX from the first <input> that has an ID
            sPrefix = $(elRow).find("input[id]").first().attr("id");
            if (sPrefix.indexOf("-") > 0) {
              sPrefix = sPrefix.substr(0, sPrefix.lastIndexOf("-")) + "-";
            } 
          }

          // Fetch value for country in this line
          country = $("input[id=" + sPrefix + "country]").val();
          // Build the URL with the components we have
          url += encodeURIComponent(uriEncodedQuery);
          // Possibly add country
          if (country) url += "&country=" + country;
          // Return the resulting URL
          return url;
        } catch (ex) {
          private_methods.errMsg("tt_city", ex);
        }
      },

      /**
       *  tt_library
       *    Bloodhound / remote / replace function for: LIBRARY
       */
      tt_library: function (url, uriEncodedQuery) {
        var elThis = loc_elInput,
            elRow = null,
            sPrefix = "id_",
            city = "",
            country = "";

        try {
          // Get to this row
          elRow = $(elThis).closest("tr").first();
          if (elRow.length > 0) {
            // Get the PREFIX from the first <input> that has an ID
            sPrefix = $(elRow).find("input[id]").first().attr("id");
            sPrefix = sPrefix.substr(0, sPrefix.lastIndexOf("-")) + "-";
          }

          // Fetch values for city and country in this line
          city = $("input[id="+sPrefix+"city]").val();
          country = $("input[id=" + sPrefix + "country]").val();
          // Build the URL with the components we have
          url += encodeURIComponent(uriEncodedQuery);
          // Possibly add country
          if (country) url += "&country=" + country;
          // Possibly add city
          if (city) url += "&city=" + city;
          // Return the resulting URL
          return url;
        } catch (ex) {
          private_methods.errMsg("tt_library", ex);
        }
      },

      /**
       *  form_submit
       *    Refer to this in an [onkeydown] item of an input box
       *    When the ENTER key is pressed, the nearest form is submitted
       */
      form_submit: function(e) {
        var target,
            frm = null;

        try {
          // Get the event
          e = e || window.event;
          if (e.keyCode == 13) {
            // Get the target
            target = e.target || e.srcElement;
            // Find the form
            frm = $(target).closest("form");
            // Make sure the GET method is used
            $(frm).attr("method", "GET");
            // Show we are waiting
            $("#waitingsign").removeClass("hidden");
            // Submit that form
            $(frm).submit();
          }
        } catch (ex) {
          private_methods.errMsg("form_submit", ex);
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
          // Set the 'action; attribute in the form
          frm.attr("action", ajaxurl);
          // Make sure we do a POST
          frm.attr("method", "POST");

          // Get the download type and put it in the <input>
          dtype = $(elStart).attr("downloadtype");
          $(frm).find("#downloadtype").val(dtype);

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

          // Check on what has been returned
          if (oBack !== null) {

          }
        } catch (ex) {
          private_methods.errMsg("post_download", ex);
        }
      },

      /**
       * lib_manuscripts
       *   Get the manuscripts of the library
       *
       */
      lib_manuscripts: function (el) {
        var url = "",
            data = "",
            items = [],
            i = 0,
            html = [],
            sBack = "",
            frm = null,
            item = "",
            libName = "",
            idVille = "",
            target = "";

        try {
          // Which site to open when ready
          target = $(el).attr("data-target");

          // Close all other sites
          $(".lib-manuscripts").addClass("hidden");

          // Open my new site and show we are working
          $(target).removeClass("hidden");
          sBack = "Searching in the library..." + loc_sWaiting;
          $(target).find(".manuscripts-target").first().html(sBack);

          // Get the parameters
          idVille = $(el).attr("city");
          libName = $(el).attr("library");
          // Prepare the request for information
          url = base_url + 'api/manuscripts/'
          frm = $(el).closest("form");
          if (frm !== undefined) { data = $(frm).serializeArray(); }
          data.push({ "name": "city", "value": idVille });
          data.push({ "name": "library", "value": libName });
          // Request the information
          $.post(url, data, function (response) {
            if (response !== undefined) {
              // There is a respons object, but can we read it?
              html = [];
              for (i = 0; i < response.length; i++) {
                item = response[i];
                html.push("<span class='manuscript'>" + item + "</span>");
              }
              sBack = html.join("\n");
              $(target).find(".manuscripts-target").first().html(sBack);
              $(target).removeClass("hidden");
            } else {
              private_methods.errMsg("lib_manuscripts: undefined response ");
            }
          });
        } catch (ex) {
          private_methods.errMsg("lib_manuscripts", ex);
        }
      },
    
      /**
       * sent_click
       *   Show waiting symbol when sentence is clicked
       *
       */
      sent_click : function() {
        $("#sentence-fetch").removeClass("hidden");
      },

      /**
       * tabinline_add_copy
       *   Add a COPY button to all tabular inlines available
       */
      tabinline_add_copy: function () {
        $(".tabular .related-widget-wrapper").each(
          function (idx, obj) {
            // Find the first <a> child
            var chgNode = $(this).children("a").first();
            var sHref = $(chgNode).attr("href");
            if (sHref !== undefined) {
              // Remove from /change onwards
              var iChangePos = sHref.lastIndexOf("/change");
              if (iChangePos > 0) {
                sHref = sHref.substr(0, sHref.lastIndexOf("/change"));
                // Get the id
                var lastSlash = sHref.lastIndexOf("/");
                var sId = sHref.substr(lastSlash + 1);
                sHref = sHref.substr(0, lastSlash);
                // Get the model name
                lastSlash = sHref.lastIndexOf("/");
                var sModel = sHref.substr(lastSlash + 1);
                sHref = sHref.substr(0, lastSlash);
                // Find and adapt the history link's content to a current
                var sCurrent = $(".historylink").first().attr("href").replace("/history", "");
                // Create a new place to go to
                sHref = sHref.replace("collection", "copy") + "/?_popup=0&model=" + sModel + "&id=" + sId + "&current=" + sCurrent;
                var sAddNode = "<a class='copy-related' title='Make a copy' href='" + sHref + "'>copy</a>";
                // Append the new node
                $(this).append(sAddNode);
              }
            }
          });
      },

      text_info_show: function (el) {
        var ajaxurl = "",
            divShow = null,
            data = null;

        try {
          // Validate
          if (el === undefined || divShow === undefined || divShow === "") {
            return;
          }
          // Find the next <tr> containing the element to be shown
          divShow = $(el).closest("tr").next("tr").find("td").first();
          // Check the status of this item
          if (!$(divShow).hasClass("hidden")) {
            // This is not a hidden item, so just close it
            $(divShow).addClass("hidden");
            return;
          }
          // Hide all the info that has been shown so far
          $(el).closest("table").find(".text-details").addClass("hidden");
          // Retrieve the URL we need to have
          ajaxurl = $(el).attr("ajaxurl");
          // Get the data: this is to get a valid csrf token!
          data = $("#textsearch").serializeArray();
          // Request the information
          $.post(ajaxurl, data, function (response) {
            if (response !== undefined) {
              switch (response.status) {
                case "ok":
                  $(divShow).html(response.html);
                  $(divShow).removeClass("hidden");
                  break;
                default:
                  private_methods.errMsg("text_info_show: incorrect response " + response.status);
                  break;
              } 
            } else {
              private_methods.errMsg("text_info_show: undefined response ");
            }
          });

        } catch (ex) {
          private_methods.errMsg("text_info_show", ex);
        }
      },

      /**
       *  sync_start
       *      Start synchronisation
       *
       */
      sync_start : function(sSyncType) {
        var oJson = {},
            oData = {},
            i,
            sParam = "",
            arKV = [],
            arParam = [],
            sUrl = "";

        // Indicate that we are starting
        $("#sync_progress_" + sSyncType).html("Synchronization is starting: " + sSyncType);

        // Make sure that at the end: we stop
        oData = { 'type': sSyncType };
        // More data may be needed for particular types
        switch (sSyncType) {
          case "texts":
            // Retrieve the parameters from the <form> settings
            sParam = $("#sync_form_" + sSyncType).serialize();
            arParam = sParam.split("&");
            for (i = 0; i < arParam.length; i++) {
              arKV = arParam[i].split("=");
              // Store the parameters into a JSON object
              oData[arKV[0]] = arKV[1];
            }
            break;
        }

        // Start looking only after some time
        oJson = { 'status': 'started' };
        ru.passim.oSyncTimer = window.setTimeout(function () { ru.passim.sync_progress(sSyncType, oJson); }, 3000);

        // Define the URL
        sUrl = $("#sync_start_" + sSyncType).attr('sync-start');
        $.ajax({
          url: sUrl,
          type: "GET",
          async: true,
          dataType: "json",
          data: oData,      // This sends the parameters in the data object
          cache: false,
          success: function (json) {
            $("#sync_details_" + sSyncType).html("start >> sync_stop");
            ru.passim.sync_stop(sSyncType, json);
          },
          failure: function () {
            $("#sync_details_" + sSyncType).html("Ajax failure");
          }
        });

      },

      /**
       *  sync_progress
       *      Return the progress of synchronization
       *
       */
      sync_progress: function (sSyncType, options) {
        var oData = {},
            sUrl = "";

        oData = { 'type': sSyncType };
        sUrl = $("#sync_start_" + sSyncType).attr('sync-progress');
        $.ajax({
          url: sUrl,
          type: "GET",
          async: true,
          dataType: "json",
          data: oData,
          cache: false,
          success: function (json) {
            $("#sync_details_" + sSyncType).html("progress >> sync_handle");
            ru.passim.sync_handle(sSyncType, json);
          },
          failure: function () {
            $("#sync_details_" + sSyncType).html("Ajax failure");
          }
        });
      },

      /**
       *  sync_handle
       *      Process synchronisation
       *
       */
      sync_handle: function (sSyncType, json) {
        var sStatus = "",
            options = {};

        // Validate
        if (json === undefined) {
          sStatus = $("#sync_details_" + sSyncType).html();
          $("#sync_details_" + sSyncType).html(sStatus + "(undefined status)");
          return;
        }
        // Action depends on the status in [json]
        switch (json.status) {
          case 'error':
            // Show we are ready
            $("#sync_progress_" + sSyncType).html("Error synchronizing: " + sSyncType);
            $("#sync_details_" + sSyncType).html(ru.passim.sync_details(json));
            // Stop the progress calling
            window.clearInterval(ru.passim.oSyncTimer);
            // Leave the routine, and don't return anymore
            return;
          case "done":
          case "finished":
            // Default action is to show the status
            $("#sync_progress_" + sSyncType).html(json.status);
            $("#sync_details_" + sSyncType).html(ru.passim.sync_details(json));
            // Finish nicely
            ru.passim.sync_stop(sSyncType, json);
            return;
          default:
            // Default action is to show the status
            $("#sync_progress_" + sSyncType).html(json.status);
            $("#sync_details_" + sSyncType).html(ru.passim.sync_details(json));
            ru.passim.oSyncTimer = window.setTimeout(function () { ru.passim.sync_progress(sSyncType, options); }, 1000);
            break;
        }
      },

      /**
       *  sync_stop
       *      Finalize synchronisation
       *
       */
      sync_stop: function (sSyncType, json) {
        var lHtml = [];

        // Stop the progress calling
        window.clearInterval(ru.passim.oSyncTimer);
        // Show we are ready
        $("#sync_progress_" + sSyncType).html("Finished synchronizing: " + sSyncType + "<br>" + JSON.stringify(json, null, 2));

      },

      /**
       *  sync_details
       *      Return a string with synchronisation details
       *
       */
      sync_details: function (json) {
        var lHtml = [],
            oCount = {};

        // Validate
        if (json === undefined || !json.hasOwnProperty("count"))
          return "";
        // Get the counts
        oCount = JSON.parse(json['count']);
        // Create a reply
        lHtml.push("<div><table><thead><tr><th></th><th></th></tr></thead><tbody>");
        for (var property in oCount) {
          if (oCount.hasOwnProperty(property)) {
            lHtml.push("<tr><td>" + property + "</td><td>" + oCount[property] + "</td></tr>");
          }
        }
        lHtml.push("</tbody></table></div>");
        // Return as string
        return lHtml.join("\n");
      },

      /**
       *  part_detail_toggle
       *      Toggle part detail
       *
       */
      part_detail_toggle: function (iPk) {
        var sId = "";

        // validate
        if (iPk === undefined) return;
        // Get the name of the tag
        sId = "#part_details_" + iPk.toString();
        // Check if it is visible or not
        if ($(sId).hasClass("hidden")) {
          // Remove it
          $(sId).removeClass("hidden");
        } else {
          // Add it
          $(sId).addClass("hidden");
        }
      },

      /**
       *  view_switch
       *      Switch from one view to the other
       *
       */
      view_switch: function (sOpen, sClose) {
        $("#" + sOpen).removeClass("hidden");
        $("#" + sClose).addClass("hidden");
        // Show/hide <li> elements
        $("li." + sOpen).removeClass("hidden");
        $("li." + sClose).addClass("hidden");
      }

    };
  }($, ru.config));

  return ru;
}(jQuery, window.ru || {})); // window.ru: see http://stackoverflow.com/questions/21507964/jslint-out-of-scope

